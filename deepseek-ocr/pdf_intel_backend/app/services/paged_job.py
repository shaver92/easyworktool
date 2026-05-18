"""多页 OCR 异步任务：落盘上传 + status.json，供 SSE 轮询进度。"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from app.config import Settings, settings as global_settings
from app.services.document_store import is_safe_document_id
from app.services.paged_pdf_parse import run_paged_ocr_and_store
from app.schemas_documents import PagedPageResult, ParsePdfPagedMeta, ParsePdfPagedResponse

logger = logging.getLogger(__name__)


def jobs_root(s: Settings) -> Path:
    return s.jobs_storage_path


def job_path(s: Settings, job_id: str) -> Path:
    return jobs_root(s) / job_id


def write_job(s: Settings, job_id: str, payload: dict[str, Any]) -> None:
    d = job_path(s, job_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_job(s: Settings, job_id: str) -> dict[str, Any]:
    p = job_path(s, job_id) / "status.json"
    if not p.is_file():
        raise FileNotFoundError(job_id)
    return json.loads(p.read_text(encoding="utf-8"))


def create_job_with_upload(s: Settings, filename: str, pdf_bytes: bytes) -> str:
    jobs_root(s).mkdir(parents=True, exist_ok=True)
    job_id = str(uuid.uuid4())
    d = job_path(s, job_id)
    d.mkdir(parents=False, exist_ok=False)
    (d / "upload.pdf").write_bytes(pdf_bytes)
    write_job(
        s,
        job_id,
        {
            "job_id": job_id,
            "status": "queued",
            "filename": filename,
            "document_id": None,
            "page_total": 0,
            "page_current": 0,
            "phase": "queued",
            "error": None,
            "warnings": [],
            "result": None,
        },
    )
    return job_id


def _merge_job(s: Settings, job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    cur = read_job(s, job_id)
    cur.update(patch)
    write_job(s, job_id, cur)
    return cur


async def run_paged_job_worker(job_id: str) -> None:
    """后台执行：读 upload.pdf → 按页 OCR → 写 result。"""
    s = global_settings
    if not is_safe_document_id(job_id):
        logger.error("非法 job_id: %s", job_id)
        return
    try:
        st = read_job(s, job_id)
    except FileNotFoundError:
        return
    if st.get("status") not in ("queued",):
        return

    upload = job_path(s, job_id) / "upload.pdf"
    if not upload.is_file():
        _merge_job(s, job_id, {"status": "failed", "error": "upload.pdf 缺失", "phase": "failed"})
        return

    pdf_bytes = upload.read_bytes()
    filename = st.get("filename") or "document.pdf"

    async def on_prog(ev: dict[str, Any]) -> None:
        patch: dict[str, Any] = {
            "status": "running",
            "phase": ev.get("phase", "running"),
            "page_current": int(ev.get("page_current", 0)),
            "page_total": int(ev.get("page_total", 0)),
        }
        if ev.get("message"):
            patch["message"] = ev["message"]
        _merge_job(s, job_id, patch)

    try:
        _merge_job(s, job_id, {"status": "running", "phase": "starting", "message": "开始处理"})
        doc_id, _dir, meta, warnings = await run_paged_ocr_and_store(
            settings=s,
            filename=filename,
            pdf_bytes=pdf_bytes,
            progress_cb=on_prog,
        )
        mock = s.use_mock or not s.siliconflow_api_key.strip()
        pages = [PagedPageResult.model_validate(p) for p in meta.pages]
        result = ParsePdfPagedResponse(
            document_id=doc_id,
            filename=meta.filename,
            page_count=meta.page_count,
            pages=pages,
            meta=ParsePdfPagedMeta(
                model_ocr=s.siliconflow_model_ocr if not mock else "mock",
                mock=mock,
                warnings=warnings,
            ),
        )
        _merge_job(
            s,
            job_id,
            {
                "status": "completed",
                "phase": "done",
                "document_id": doc_id,
                "page_total": meta.page_count,
                "page_current": meta.page_count,
                "warnings": warnings,
                "result": result.model_dump(),
                "message": "完成",
            },
        )
    except ValueError as e:
        _merge_job(
            s,
            job_id,
            {"status": "failed", "phase": "failed", "error": str(e), "message": str(e)},
        )
    except Exception as e:
        logger.exception("异步 OCR 任务失败 job=%s", job_id)
        _merge_job(
            s,
            job_id,
            {"status": "failed", "phase": "failed", "error": str(e), "message": str(e)[:500]},
        )
