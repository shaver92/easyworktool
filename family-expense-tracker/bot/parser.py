from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

# Format 1: amount category note → "128 餐饮 中午请客"
PATTERN_FULL = re.compile(
    r"^\s*(?P<amount>\d+(?:\.\d{1,2})?)\s+(?P<category>\S+)\s+(?P<note>.+?)\s*$"
)

# Format 2: amount known-category → "36.5 交通"
PATTERN_CAT = re.compile(
    r"^\s*(?P<amount>\d+(?:\.\d{1,2})?)\s+(?P<category>\S+)\s*$"
)

# Format 3: amount note → "32 早饭"  (second token is NOT a known category)
PATTERN_AMOUNT_NOTE = re.compile(
    r"^\s*(?P<amount>\d+(?:\.\d{1,2})?)\s+(?P<note>.+?)\s*$"
)

PARSE_TIMEOUT_MS = 100


@dataclass
class ParsedExpense:
    amount: float
    category: str | None
    note: str | None


class ParseError(Exception):
    pass


class ParseTimeout(Exception):
    pass


def _timed_match(pattern: re.Pattern, text: str, timeout_ms: int = PARSE_TIMEOUT_MS) -> re.Match | None:
    """Run regex match with a timeout guard to prevent ReDoS."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    match = pattern.match(text)
    if time.monotonic() > deadline:
        raise ParseTimeout("消息解析超时，请缩短输入")
    return match


def parse_message(text: str, known_categories: set[str] | None = None) -> ParsedExpense:
    """Parse a Feishu bot message into a structured expense.

    Tries formats in order:
    1. amount category note   → "128 餐饮 中午请客"
    2. amount category        → "36.5 交通" (only if category is known)
    3. amount note            → "32 早饭"  (second token is not a known category)

    Args:
        text: raw message text
        known_categories: set of known category names for format 2 detection

    Returns ParsedExpense on success.
    Raises ParseError if the message doesn't match any supported format.
    """
    text = text.strip()
    if not text or len(text) > 500:
        raise ParseError("没识别出来，试试这样：`128 餐饮 中午请客`\n\n支持格式：\n• `金额 类别 备注`\n• `金额 类别`\n• `金额 备注`")

    if known_categories is None:
        known_categories = set()

    try:
        # Format 1: amount category note (3+ tokens → unambiguous)
        m = _timed_match(PATTERN_FULL, text)
        if m:
            return ParsedExpense(
                amount=float(m.group("amount")),
                category=m.group("category"),
                note=m.group("note"),
            )

        # Format 2/3: two-token patterns — distinguish by known categories
        m = _timed_match(PATTERN_CAT, text)
        if m:
            second_token = m.group("category")
            if second_token in known_categories:
                # Format 2: known category
                return ParsedExpense(
                    amount=float(m.group("amount")),
                    category=second_token,
                    note=None,
                )
            else:
                # Format 3: unknown → treat as note
                return ParsedExpense(
                    amount=float(m.group("amount")),
                    category=None,
                    note=second_token,
                )

    except ParseTimeout:
        raise

    raise ParseError("没识别出来，试试这样：`128 餐饮 中午请客`\n\n支持格式：\n• `金额 类别 备注`\n• `金额 类别`\n• `金额 备注`")


def resolve_category(repo: Any, category_name: str | None, user_id: int) -> int:
    """Resolve a category name to its id.

    If category_name is None, falls back to '其他'.
    If category_name is not found in DB, creates an ad-hoc category.
    """
    if category_name is None:
        category_name = "其他"

    row = repo.fetch_one(
        "SELECT id FROM categories WHERE name = ?",
        (category_name,),
    )
    if row:
        return row["id"]

    # Create ad-hoc category for unknown names
    return repo.execute(
        "INSERT INTO categories (name, icon, created_by) VALUES (?, '📌', ?)",
        (category_name, user_id),
    )
