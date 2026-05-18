"""多页 PDF 解析（按页 OCR 落盘）、异步任务 + SSE、基于文档的聊天。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from openai import APIError, APITimeoutError

from app.config import settings
from app.schemas_documents import (
    DocumentChatRequest,
    DocumentChatResponse,
    DocumentInfoResponse,
    JobQueuedResponse,
    ParsePdfPagedMeta,
    ParsePdfPagedResponse,
    PagedPageResult,
)
from app.services.document_context import (
    build_excerpt_for_page_order,
    rank_pages_by_keywords,
)
from app.services.document_store import (
    iter_page_markdowns,
    read_meta,
    read_page_markdown,
    resolve_document_dir,
)
from app.services.paged_job import (
    create_job_with_upload,
    read_job,
    run_paged_job_worker,
)
from app.services.paged_pdf_parse import run_paged_ocr_and_store
from app.services.siliconflow_chat import document_qa_chat
from app.services.siliconflow_page_router import mock_route_pages, route_pages_with_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _normalize_chat_messages(raw: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in raw:
        role = (getattr(m, "role", "") or "").strip()
        content = (getattr(m, "content", "") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if not out:
            if role != "user":
                continue
            out.append({"role": role, "content": content})
            continue
        if out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    return out


def _last_user_query(messages: list[Any]) -> str:
    for m in reversed(messages):
        if getattr(m, "role", None) == "user" and (getattr(m, "content", None) or "").strip():
            return m.content.strip()
    return ""


def _conversation_tail(msg_dicts: list[dict[str, str]], max_chars: int = 1200) -> str:
    parts: list[str] = []
    n = 0
    for m in msg_dicts[-6:]:
        line = f"{m['role']}: {m['content']}"
        n += len(line)
        if n > max_chars:
            break
        parts.append(line)
    return "\n".join(parts)


def _build_router_snippets(
    pairs: list[tuple[int, str]],
    candidate_pages: list[int],
    per_snip: int,
    catalog_max: int,
) -> list[tuple[int, str]]:
    pmap = {p: t for p, t in pairs}
    snip = per_snip
    while snip >= 80:
        snippets: list[tuple[int, str]] = []
        used = 0
        for p in candidate_pages:
            if p not in pmap:
                continue
            body = pmap[p][:snip] + ("…" if len(pmap[p]) > snip else "")
            block = f"第{p}页:{body}"
            if used + len(block) + 2 > catalog_max:
                break
            snippets.append((p, body))
            used += len(block) + 2
        if used <= catalog_max or snip <= 80:
            return snippets
        snip = max(80, int(snip * 0.75))
    return []


# --- 异步任务 + SSE（须写在 /{document_id} 之前，避免被误匹配）---


@router.post("/parse-paged-async", response_model=JobQueuedResponse)
async def parse_pdf_paged_async(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> JobQueuedResponse:
    """
    接收 PDF 后立即返回 job_id；OCR 在后台执行。
    客户端订阅 GET `/api/documents/jobs/{job_id}/events`（SSE）或轮询 GET `/api/documents/jobs/{job_id}`。
    """
    name = (file.filename or "").strip()
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传扩展名为 .pdf 的文件")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="文件超过大小限制")

    job_id = create_job_with_upload(settings, name, raw)
    background_tasks.add_task(run_paged_job_worker, job_id)
    return JobQueuedResponse(
        job_id=job_id,
        events_url=f"/api/documents/jobs/{job_id}/events",
        status_url=f"/api/documents/jobs/{job_id}",
    )


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    try:
        return read_job(settings, job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="任务不存在") from None


@router.get("/jobs/{job_id}/events")
async def job_events_stream(job_id: str) -> StreamingResponse:
    """SSE：推送 status.json 全量快照，直至 completed / failed。"""

    async def gen():
        max_ticks = 100_000
        for _ in range(max_ticks):
            try:
                payload = read_job(settings, job_id)
            except FileNotFoundError:
                yield "data: {\"error\":\"not_found\"}\n\n"
                break
            line = "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
            yield line
            st = payload.get("status")
            if st in ("completed", "failed"):
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- 同步按页解析（保留） ---


@router.post("/parse-paged", response_model=ParsePdfPagedResponse)
async def parse_pdf_paged(file: UploadFile = File(...)) -> ParsePdfPagedResponse:
    name = (file.filename or "").strip()
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传扩展名为 .pdf 的文件")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="文件超过大小限制")

    try:
        doc_id, _dir, meta, warnings = await run_paged_ocr_and_store(
            settings=settings,
            filename=name,
            pdf_bytes=raw,
            progress_cb=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        logger.exception("按页解析失败")
        raise HTTPException(status_code=500, detail=str(e)) from None

    mock = settings.use_mock or not settings.siliconflow_api_key.strip()
    pages = [PagedPageResult.model_validate(p) for p in meta.pages]

    return ParsePdfPagedResponse(
        document_id=doc_id,
        filename=meta.filename,
        page_count=meta.page_count,
        pages=pages,
        meta=ParsePdfPagedMeta(
            model_ocr=settings.siliconflow_model_ocr if not mock else "mock",
            mock=mock,
            warnings=warnings,
        ),
    )


@router.get("/{document_id}", response_model=DocumentInfoResponse)
def get_document(document_id: str) -> DocumentInfoResponse:
    try:
        doc_dir = resolve_document_dir(settings.documents_storage_path, document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 document_id") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文档不存在") from None

    meta = read_meta(doc_dir)
    pages = [PagedPageResult.model_validate(p) for p in meta.get("pages", [])]
    return DocumentInfoResponse(
        document_id=meta["document_id"],
        filename=meta.get("filename", ""),
        page_count=int(meta.get("page_count", 0)),
        pages=pages,
        created_at=meta.get("created_at", ""),
    )


@router.get("/{document_id}/export.md")
def export_all_markdown(document_id: str) -> Response:
    try:
        doc_dir = resolve_document_dir(settings.documents_storage_path, document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 document_id") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文档不存在") from None

    meta = read_meta(doc_dir)
    page_count = int(meta.get("page_count", 0))
    chunks: list[str] = []
    for i in range(1, page_count + 1):
        try:
            md = read_page_markdown(doc_dir, i)
        except FileNotFoundError:
            md = ""
        chunks.append(f"\n\n---\n\n# 第 {i} 页\n\n{md.strip()}")

    body = "\n".join(chunks).strip() + "\n"
    ascii_name = f"{document_id[:8]}-all-pages.md"
    return Response(
        content=body.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{ascii_name}',
        },
    )


@router.get("/{document_id}/pages/{page_no}/markdown")
def get_page_markdown(document_id: str, page_no: int) -> dict[str, str]:
    if page_no < 1:
        raise HTTPException(status_code=400, detail="page_no 须 ≥ 1")
    try:
        doc_dir = resolve_document_dir(settings.documents_storage_path, document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 document_id") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文档不存在") from None

    meta = read_meta(doc_dir)
    pc = int(meta.get("page_count", 0))
    if page_no > pc:
        raise HTTPException(status_code=404, detail="页码超出范围")

    try:
        text = read_page_markdown(doc_dir, page_no)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="该页 Markdown 不存在") from None

    return {"page": str(page_no), "markdown": text}


@router.post("/{document_id}/chat", response_model=DocumentChatResponse)
async def document_chat(document_id: str, body: DocumentChatRequest) -> DocumentChatResponse:
    try:
        doc_dir = resolve_document_dir(settings.documents_storage_path, document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 document_id") from None
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文档不存在") from None

    meta = read_meta(doc_dir)
    page_count = int(meta.get("page_count", 0))
    pairs = iter_page_markdowns(doc_dir, page_count)
    if not pairs:
        raise HTTPException(status_code=404, detail="未找到任何页面内容")

    user_q = _last_user_query(body.messages)
    msg_dicts = _normalize_chat_messages(body.messages)
    if not msg_dicts:
        raise HTTPException(status_code=400, detail="请至少提供一条有效的 user 消息")

    tail = _conversation_tail(msg_dicts)

    mock = settings.use_mock or not settings.siliconflow_api_key.strip()

    pre_n = settings.doc_router_prefilter_pages
    if len(pairs) <= pre_n:
        candidate_pages = [p for p, _ in pairs]
    else:
        q = user_q or "概述文档主要内容"
        candidate_pages = rank_pages_by_keywords(pairs, q, pre_n)

    snippets = _build_router_snippets(
        pairs,
        candidate_pages,
        settings.doc_page_router_snippet_chars,
        settings.doc_router_catalog_max_chars,
    )

    router_pages: list[int] = []
    if mock:
        router_pages = mock_route_pages(page_count, settings.doc_page_router_max_pick)
    elif not snippets:
        q0 = user_q or "文档"
        router_pages = rank_pages_by_keywords(pairs, q0, settings.doc_page_router_max_pick)
    else:
        try:
            rq = user_q or "请根据摘录判断哪些页与对话最相关"
            router_pages = await route_pages_with_llm(
                api_key=settings.siliconflow_api_key,
                base_url=settings.siliconflow_base_url.rstrip("/"),
                model=settings.router_llm_model,
                user_query=rq,
                conversation_tail=tail,
                page_snippets=snippets,
                timeout_sec=settings.doc_page_router_timeout_sec,
                max_tokens=settings.doc_page_router_max_tokens,
                max_pick=settings.doc_page_router_max_pick,
            )
        except (APIError, APITimeoutError) as e:
            logger.warning("页码路由失败，回退关键词: %s", e)
            router_pages = []
        except Exception as e:
            logger.warning("页码路由异常，回退关键词: %s", e)
            router_pages = []

    if not router_pages:
        q2 = user_q or "文档"
        router_pages = rank_pages_by_keywords(pairs, q2, settings.doc_page_router_max_pick)

    excerpt, used_pages = build_excerpt_for_page_order(
        pairs,
        router_pages,
        settings.doc_chat_max_context_chars,
    )

    if mock:
        note = (
            f"MOCK：未调用 Qwen 对话。路由页（模拟）{router_pages[:8]}{'…' if len(router_pages) > 8 else ''}；"
            f"摘录约 {len(excerpt)} 字符，实际送入对话页 {used_pages}。"
        )
        return DocumentChatResponse(
            reply=(
                "（MOCK 回复）当前为联调模式或未配置 SILICONFLOW_API_KEY，"
                "无法调用真实对话模型。请配置密钥后重试。"
            ),
            pages_in_context=used_pages,
            context_chars=len(excerpt),
            note=note,
            router_pages=router_pages,
        )

    try:
        reply = await document_qa_chat(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url.rstrip("/"),
            model=settings.siliconflow_model_qwen,
            document_excerpt=excerpt,
            messages=msg_dicts,
            timeout_sec=settings.llm_timeout_sec,
            max_tokens=settings.doc_chat_max_tokens,
        )
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="文档对话请求超时") from None
    except APIError as e:
        logger.exception("文档对话失败")
        raise HTTPException(status_code=502, detail=f"文档对话失败: {e}") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        logger.exception("文档对话异常")
        raise HTTPException(status_code=500, detail=str(e)) from None

    note = (
        f"大模型路由页：{router_pages[:15]}{'…' if len(router_pages) > 15 else ''}；"
        f"因长度限制实际送入对话的页：{used_pages}（约 {len(excerpt)} 字符）。"
    )
    return DocumentChatResponse(
        reply=reply,
        pages_in_context=used_pages,
        context_chars=len(excerpt),
        note=note,
        router_pages=router_pages,
    )
