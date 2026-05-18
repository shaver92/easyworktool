#!/usr/bin/env python3
"""本机流水线验证：OCR +（可选）Qwen；不打印 API Key。"""
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
    from app.services.siliconflow_llm import markdown_to_structured
    from app.services.siliconflow_ocr import ocr_pdf_to_markdown

    print("=== 配置（不含密钥）===")
    print("ocr_enabled:", settings.ocr_enabled)
    print("use_mock:", settings.use_mock)
    print("skip_qwen:", settings.skip_qwen)
    print("model_ocr:", settings.siliconflow_model_ocr)
    print("model_qwen:", settings.siliconflow_model_qwen)
    print("base_url:", settings.siliconflow_base_url)
    print("key_present:", bool(settings.siliconflow_api_key.strip()))

    if settings.use_mock or not settings.siliconflow_api_key.strip():
        print("\n当前会走 MOCK：请检查 .env 中 SILICONFLOW_API_KEY 非空且 USE_MOCK 不为 true")
        return 1

    minimal_pdf = b"""%PDF-1.4
1 0 obj<<>>endobj
trailer<<>>
%%EOF
"""
    print("\n=== 1) DeepSeek-OCR ===")
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

    print("markdown_len:", len(md))

    if settings.skip_qwen:
        print("\n已 SILICONFLOW_SKIP_QWEN=true，跳过 Qwen。")
        return 0

    print("\n=== 2) Qwen 结构化 ===")
    try:
        st = await markdown_to_structured(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url.rstrip("/"),
            model=settings.siliconflow_model_qwen,
            markdown=md[:8000],
            timeout_sec=min(settings.llm_timeout_sec, 120.0),
        )
    except Exception as e:
        print("Qwen 失败:", type(e).__name__, str(e)[:500])
        return 3

    print("title:", st.title[:200])
    print("summary:", st.summary[:300])
    print("key_points:", len(st.key_points), "action_items:", len(st.action_items))
    print("\n流水线验证通过。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
