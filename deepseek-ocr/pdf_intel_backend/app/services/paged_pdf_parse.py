"""PDF 按页拆分并逐页 OCR，结果写入 document_store。"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from openai import APIError, APITimeoutError

from app.config import Settings
from app.services.document_store import (
    StoredDocumentMeta,
    create_document_dir,
    page_md_path,
    utc_now_iso,
    write_meta,
)
from app.services.pdf_split import split_pdf_to_single_page_pdfs
from app.services.siliconflow_ocr import ocr_pdf_to_markdown

logger = logging.getLogger(__name__)

ProgressCb = Callable[[dict[str, Any]], Awaitable[None]] | None


async def run_paged_ocr_and_store(
    *,
    settings: Settings,
    filename: str,
    pdf_bytes: bytes,
    progress_cb: ProgressCb = None,
) -> tuple[str, Path, StoredDocumentMeta, list[str]]:
    """
    返回 (document_id, doc_dir, meta, warnings)。
    单页失败时写入占位 Markdown，并在 meta.pages[].error 记录。
    progress_cb 接收如 {"phase": "ocr", "page_current": i, "page_total": n}。
    """
    warnings: list[str] = []
    page_pdfs = split_pdf_to_single_page_pdfs(pdf_bytes)
    if not page_pdfs:
        raise ValueError("PDF 无页面或无法读取")

    if len(page_pdfs) > settings.max_pdf_pages_paged:
        raise ValueError(
            f"页数 {len(page_pdfs)} 超过上限 {settings.max_pdf_pages_paged}，请拆分 PDF 或调大环境变量 MAX_PDF_PAGES_PAGED"
        )

    if progress_cb:
        await progress_cb(
            {
                "phase": "splitting",
                "page_current": 0,
                "page_total": len(page_pdfs),
                "message": "已拆分 PDF",
            }
        )

    doc_id, doc_dir = create_document_dir(settings.documents_storage_path)
    pages_meta: list[dict] = []

    mock = settings.use_mock or not settings.siliconflow_api_key.strip()

    for i, single_pdf in enumerate(page_pdfs, start=1):
        err: str | None = None
        md = ""
        if progress_cb:
            await progress_cb(
                {
                    "phase": "ocr",
                    "page_current": i,
                    "page_total": len(page_pdfs),
                    "message": f"正在 OCR 第 {i}/{len(page_pdfs)} 页",
                }
            )
        try:
            if mock:
                md = (
                    f"# Mock 第 {i} 页\n\n"
                    f"（USE_MOCK 或未配置 SILICONFLOW_API_KEY；原文件 `{filename}`）\n\n"
                    f"占位 Markdown，用于联调多页存储与对话。\n"
                )
            else:
                md = await ocr_pdf_to_markdown(
                    api_key=settings.siliconflow_api_key,
                    base_url=settings.siliconflow_base_url.rstrip("/"),
                    model=settings.siliconflow_model_ocr,
                    pdf_bytes=single_pdf,
                    timeout_sec=settings.ocr_timeout_sec,
                    max_tokens=settings.siliconflow_ocr_max_tokens,
                )
        except APITimeoutError:
            err = f"第 {i} 页 OCR 超时"
            logger.warning("%s", err)
            md = f"<!-- OCR 失败: {err} -->\n\n"
            warnings.append(err)
        except APIError as e:
            err = f"第 {i} 页 OCR API 错误: {e}"
            logger.warning("%s", err)
            md = f"<!-- OCR 失败 -->\n\n```\n{str(e)[:2000]}\n```\n"
            warnings.append(err[:500])
        except Exception as e:
            err = f"第 {i} 页 OCR 异常: {e}"
            logger.exception("%s", err)
            md = "<!-- OCR 失败 -->\n\n"
            warnings.append(str(e)[:500])

        page_md_path(doc_dir, i).write_text(md, encoding="utf-8")
        pages_meta.append(
            {
                "page": i,
                "char_count": len(md),
                "ok": err is None,
                "error": err,
            }
        )

    meta = StoredDocumentMeta(
        document_id=doc_id,
        filename=filename,
        created_at=utc_now_iso(),
        page_count=len(page_pdfs),
        pages=pages_meta,
    )
    write_meta(doc_dir, meta)
    return doc_id, doc_dir, meta, warnings
