"""基于文档上下文的硅基 Qwen 多轮对话（OpenAI 兼容）。"""

import logging

from openai import APIError, AsyncOpenAI, APITimeoutError

logger = logging.getLogger(__name__)

_SYSTEM_DOC_CHAT = """你是一个文档问答助手。系统消息中的「文档摘录」来自 PDF 按页 OCR 的 Markdown，可能不是全书全文。
请只根据摘录中的信息回答；若摘录中没有足够依据，请明确说明无法从已提供的页面中判断，不要编造。"""


async def document_qa_chat(
    *,
    api_key: str,
    base_url: str,
    model: str,
    document_excerpt: str,
    messages: list[dict[str, str]],
    timeout_sec: float = 120.0,
    max_tokens: int = 2048,
) -> str:
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_sec)
    excerpt = document_excerpt.strip()
    system_content = f"{_SYSTEM_DOC_CHAT}\n\n【文档摘录】\n{excerpt}"

    api_messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    for m in messages[-24:]:
        role = (m.get("role") or "").strip()
        if role not in ("user", "assistant"):
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue
        api_messages.append({"role": role, "content": content})

    if len(api_messages) == 1:
        raise ValueError("至少需要一条 user 或 assistant 对话内容")

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=api_messages,
            max_tokens=max_tokens,
            temperature=0.3,
        )
    except APITimeoutError as e:
        logger.warning("文档对话超时: %s", e)
        raise
    except APIError as e:
        logger.warning("文档对话 APIError: %s", e)
        raise

    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("模型返回空内容")
    return text
