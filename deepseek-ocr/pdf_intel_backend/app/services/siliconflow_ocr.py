import base64
import logging

from openai import APIError, AsyncOpenAI, APITimeoutError

logger = logging.getLogger(__name__)

_OCR_PROMPT = "<image>\n<|grounding|>Convert the document to markdown."


def _pdf_data_url(pdf_bytes: bytes) -> str:
    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
    return f"data:application/pdf;base64,{b64}"


async def ocr_pdf_to_markdown(
    *,
    api_key: str,
    base_url: str,
    model: str,
    pdf_bytes: bytes,
    timeout_sec: float = 300.0,
    max_tokens: int = 4096,
) -> str:
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_sec)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _pdf_data_url(pdf_bytes),
                                "detail": "high",
                            },
                        },
                        {"type": "text", "text": _OCR_PROMPT},
                    ],
                }
            ],
            max_tokens=max_tokens,
        )
    except APITimeoutError as e:
        logger.warning("SiliconFlow OCR timeout: %s", e)
        raise
    except APIError as e:
        logger.warning("SiliconFlow OCR APIError: %s", e)
        raise

    msg = resp.choices[0].message
    text = (msg.content or "").strip()
    if not text:
        raise RuntimeError("OCR 返回空内容")
    return text
