"""用大模型根据用户问题从各页摘录中选出相关页码。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import APIError, AsyncOpenAI, APITimeoutError

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM = """你是「页码路由」模块。下面给出多页 OCR 的短摘录（每页一段，可能截断）以及用户最新问题（可能附简短对话摘要）。
你的任务：判断哪些页**最可能**包含回答该问题所需的依据。

输出要求（必须严格遵守）：
1. 只输出一个 JSON 数组，元素为整数页码（从 1 开始），最多 {max_pick} 个。
2. 按「与问题相关程度」从高到低排列；完全无关则输出 []。
3. 不要输出任何解释、不要 markdown 代码围栏、不要其它文字。"""


def _parse_page_array(text: str, max_page: int, max_pick: int) -> list[int]:
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s)
    if fence:
        s = fence.group(1).strip()
    m = re.search(r"\[[\s\d,]*\]", s)
    if m:
        s = m.group(0)
    try:
        arr = json.loads(s)
    except json.JSONDecodeError:
        return []
    if not isinstance(arr, list):
        return []
    out: list[int] = []
    for x in arr:
        if isinstance(x, int) and 1 <= x <= max_page and x not in out:
            out.append(x)
        elif isinstance(x, float) and x == int(x):
            v = int(x)
            if 1 <= v <= max_page and v not in out:
                out.append(v)
        if len(out) >= max_pick:
            break
    return out


async def route_pages_with_llm(
    *,
    api_key: str,
    base_url: str,
    model: str,
    user_query: str,
    conversation_tail: str,
    page_snippets: list[tuple[int, str]],
    timeout_sec: float,
    max_tokens: int,
    max_pick: int,
) -> list[int]:
    """
    page_snippets: (页码, 该页截断后的文本)，调用模型返回相关页码列表。
    """
    if not page_snippets:
        return []
    max_page = max(p for p, _ in page_snippets)
    lines: list[str] = []
    for p, snip in page_snippets:
        lines.append(f"--- 第 {p} 页 ---\n{snip.strip()}")
    catalog = "\n\n".join(lines)
    user_block = (
        f"用户最新问题：\n{user_query.strip()}\n\n"
        f"近期对话摘要（可为空）：\n{conversation_tail.strip() or '（无）'}\n\n"
        f"各页摘录：\n{catalog}"
    )
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_sec)
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _ROUTER_SYSTEM.format(max_pick=max_pick)},
                {"role": "user", "content": user_block},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
        )
    except APITimeoutError:
        logger.warning("页码路由模型超时")
        raise
    except APIError as e:
        logger.warning("页码路由 APIError: %s", e)
        raise

    raw = (resp.choices[0].message.content or "").strip()
    if not raw:
        return []
    return _parse_page_array(raw, max_page=max_page, max_pick=max_pick)


def mock_route_pages(page_count: int, max_pick: int) -> list[int]:
    return [p for p in range(1, min(page_count, max_pick) + 1)]
