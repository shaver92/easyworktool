"""页选择上下文：关键词排序 + 按给定页序贪心拼摘录。"""

from __future__ import annotations

import re
from collections import defaultdict


def _terms_from_query(query: str) -> list[str]:
    parts: list[str] = []
    for m in re.finditer(r"[A-Za-z]{2,}", query):
        parts.append(m.group(0).lower())
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", query):
        parts.append(m.group(0))
    return list(dict.fromkeys(parts))


def _page_block(page: int, text: str) -> str:
    return f"\n\n## 第 {page} 页\n\n{text.strip()}"


def rank_pages_by_keywords(
    page_contents: list[tuple[int, str]],
    query: str,
    top_k: int,
) -> list[int]:
    """按关键词命中次数对页排序，返回页码列表（降序相关度）。"""
    if not page_contents or top_k <= 0:
        return []
    terms = _terms_from_query(query)
    scores: dict[int, int] = defaultdict(int)
    for page, text in page_contents:
        low = text.lower()
        for t in terms:
            if t.isascii():
                if t in low:
                    scores[page] += 1
            elif t in text:
                scores[page] += 1
    ordered = sorted(page_contents, key=lambda x: (-scores[x[0]], x[0]))
    return [p for p, _ in ordered[:top_k]]


def build_excerpt_for_page_order(
    page_contents: list[tuple[int, str]],
    page_order: list[int],
    max_chars: int,
) -> tuple[str, list[int]]:
    """
    按 page_order 的优先级依次把整页 Markdown 拼入摘录，直到 max_chars。
    page_order 中不在文档内的页码会跳过。
    """
    pmap = {p: t for p, t in page_contents}
    out_chunks: list[str] = []
    used: list[int] = []
    total = 0
    for p in page_order:
        if p not in pmap:
            continue
        part = _page_block(p, pmap[p])
        if total + len(part) <= max_chars:
            out_chunks.append(part)
            used.append(p)
            total += len(part)
            continue
        slack = max_chars - total
        if slack > 80:
            out_chunks.append(part[:slack])
            used.append(p)
        break
    if not out_chunks and page_contents:
        p, text = sorted(page_contents, key=lambda x: x[0])[0]
        part = _page_block(p, text)[:max_chars]
        return part.strip(), [p]
    return "".join(out_chunks).strip(), sorted(set(used))


def build_pages_context(
    page_contents: list[tuple[int, str]],
    user_query: str,
    max_chars: int,
) -> tuple[str, list[int]]:
    """
    兼容旧逻辑：将 (页码, markdown) 拼成模型上下文。
    超长时按用户问题中的关键词对页打分，优先纳入相关页，再按序累加直至上限。
    """
    if not page_contents:
        return "", []

    blocks = [(p, _page_block(p, t)) for p, t in page_contents]
    full = "".join(b for _, b in blocks)
    if len(full) <= max_chars:
        return full.strip(), [p for p, _ in blocks]

    order = rank_pages_by_keywords(page_contents, user_query, len(page_contents))
    return build_excerpt_for_page_order(page_contents, order, max_chars)
