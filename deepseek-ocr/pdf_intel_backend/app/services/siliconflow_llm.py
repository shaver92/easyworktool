import json
import logging
import re
from typing import Any

from openai import APIError, AsyncOpenAI, APITimeoutError

from app.schemas import StructuredSummary

logger = logging.getLogger(__name__)

_SYSTEM = """你是一个文档分析助手。用户会提供从 PDF OCR 得到的 Markdown。请只根据 Markdown 中的信息提取结构化摘要，不得编造 Markdown 未出现的事实。
你必须只输出一个 JSON 对象，不要使用 markdown 代码围栏，不要在 JSON 前后添加任何说明文字。
JSON 必须包含且仅使用以下键（值可为空字符串或空数组，但键不可省略）：
- title: string
- summary: string
- key_points: string[]
- action_items: 数组，每项为对象，键为 task(string)、owner(string 或 null)、due(string 或 null)"""


def _extract_json_object(text: str) -> dict[str, Any]:
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s)
    if fence:
        s = fence.group(1).strip()
    return json.loads(s)


async def markdown_to_structured(
    *,
    api_key: str,
    base_url: str,
    model: str,
    markdown: str,
    timeout_sec: float = 120.0,
) -> StructuredSummary:
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_sec)
    user_msg = "以下是从 PDF OCR 得到的 Markdown，请输出 JSON：\n\n" + markdown
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=4096,
            temperature=0.2,
        )
    except APITimeoutError as e:
        logger.warning("Qwen 请求超时: %s", e)
        raise
    except APIError as e:
        logger.warning("Qwen APIError: %s", e)
        raise

    raw = (resp.choices[0].message.content or "").strip()
    if not raw:
        raise RuntimeError("Qwen 返回空内容")
    data = _extract_json_object(raw)
    return StructuredSummary.model_validate(data)
