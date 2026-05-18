#!/usr/bin/env python3
"""本机 Phase 2 验证：读取与 pdf_intel_backend 同目录的 .env，不打印 API Key。"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


async def _main() -> int:
    sys.path.insert(0, str(_BACKEND_ROOT))
    os.chdir(_BACKEND_ROOT)

    from app.config import settings
    from app.services.siliconflow_ocr import ocr_pdf_to_markdown

    print("=== 配置（不含密钥）===")
    print("ocr_enabled:", settings.ocr_enabled)
    print("use_mock:", settings.use_mock)
    print("model_ocr:", settings.siliconflow_model_ocr)
    print("base_url:", settings.siliconflow_base_url)
    print("key_present:", bool(settings.siliconflow_api_key.strip()))
    print("key_len:", len(settings.siliconflow_api_key.strip()))

    if settings.use_mock or not settings.siliconflow_api_key.strip():
        print("\n当前会走 MOCK：请检查 .env 中 SILICONFLOW_API_KEY 非空且 USE_MOCK 不为 true")
        return 1

    minimal_pdf = b"""%PDF-1.4
1 0 obj<<>>endobj
trailer<<>>
%%EOF
"""
    print("\n=== 调用 SiliconFlow DeepSeek-OCR（最小 PDF）===")
    try:
        md = await ocr_pdf_to_markdown(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url.rstrip("/"),
            model=settings.siliconflow_model_ocr,
            pdf_bytes=minimal_pdf,
            timeout_sec=min(settings.ocr_timeout_sec, 120.0),
        )
    except Exception as e:
        print("OCR 失败:", type(e).__name__, str(e)[:500])
        return 2

    preview = md[:800] + ("…" if len(md) > 800 else "")
    print("markdown_len:", len(md))
    print("markdown_preview:\n", preview)
    print("\nPhase 2 直连 OCR：若上方有合理文本或结构，即验证通过。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
