import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import APIError, APITimeoutError

from app.config import settings
from app.routers import documents as documents_router
from app.schemas import ParseMeta, ParsePdfResponse, mock_parse_response
from app.services.siliconflow_llm import markdown_to_structured
from app.services.siliconflow_ocr import ocr_pdf_to_markdown

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("pdf_intel_backend 启动完成（OCR + Qwen 流水线）")
    yield


app = FastAPI(title="pdf_intel_backend", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str | int | bool]:
    return {
        "status": "ok",
        "phase": 5,
        "ocr_live": settings.ocr_enabled,
        "use_mock": settings.use_mock,
        "skip_qwen": settings.skip_qwen,
        "documents_storage": str(settings.documents_storage_path),
        "jobs_storage": str(settings.jobs_storage_path),
    }


@app.post("/api/parse-pdf", response_model=ParsePdfResponse)
async def parse_pdf(file: UploadFile = File(...)) -> ParsePdfResponse:
    """
    PDF → SiliconFlow DeepSeek-OCR（Markdown）→ Qwen 结构化（可降级）。
    `USE_MOCK=true` 或未配置 `SILICONFLOW_API_KEY` 时返回固定 mock。
    `SILICONFLOW_SKIP_QWEN=true` 时仅 OCR，`structured` 为 null。
    """
    name = (file.filename or "").strip()
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传扩展名为 .pdf 的文件")

    raw = await file.read()
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="文件超过大小限制")

    if settings.use_mock or not settings.siliconflow_api_key.strip():
        return mock_parse_response(name, len(raw))

    warnings: list[str] = []

    try:
        markdown = await ocr_pdf_to_markdown(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url.rstrip("/"),
            model=settings.siliconflow_model_ocr,
            pdf_bytes=raw,
            timeout_sec=settings.ocr_timeout_sec,
            max_tokens=settings.siliconflow_ocr_max_tokens,
        )
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="SiliconFlow OCR 请求超时") from None
    except APIError as e:
        logger.exception("SiliconFlow OCR 失败")
        detail = str(e) or getattr(e, "message", None) or repr(e)
        raise HTTPException(status_code=502, detail=f"SiliconFlow OCR 失败: {detail}") from None
    except Exception as e:
        logger.exception("OCR 异常")
        raise HTTPException(status_code=502, detail=str(e)) from None

    md_for_qwen = markdown
    truncated_total: int | None = None
    if len(markdown) > settings.max_markdown_chars_for_qwen:
        md_for_qwen = markdown[: settings.max_markdown_chars_for_qwen]
        truncated_total = len(markdown)
        warnings.append(
            f"Markdown 已截断至 {settings.max_markdown_chars_for_qwen} 字符后送 Qwen（原文 {len(markdown)} 字符）"
        )

    structured = None
    model_llm: str | None = None

    if settings.skip_qwen:
        warnings.append("已设置 SILICONFLOW_SKIP_QWEN=true，跳过 Qwen，`structured` 为 null")
    else:
        try:
            structured = await markdown_to_structured(
                api_key=settings.siliconflow_api_key,
                base_url=settings.siliconflow_base_url.rstrip("/"),
                model=settings.siliconflow_model_qwen,
                markdown=md_for_qwen,
                timeout_sec=settings.llm_timeout_sec,
            )
            model_llm = settings.siliconflow_model_qwen
        except Exception as e:
            logger.exception("Qwen 结构化失败，降级为仅 Markdown")
            warnings.append(f"Qwen 结构化失败（已降级）：{str(e)[:400]}")

    return ParsePdfResponse(
        markdown=markdown,
        structured=structured,
        meta=ParseMeta(
            model_ocr=settings.siliconflow_model_ocr,
            model_llm=model_llm,
            warnings=warnings,
            mock=False,
            truncated_chars=truncated_total,
        ),
    )
