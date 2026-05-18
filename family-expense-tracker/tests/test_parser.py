from __future__ import annotations

import pytest
from bot.parser import parse_message, resolve_category, ParseError, ParsedExpense


class TestParseFullFormat:
    """Format 1: amount category note → "128 餐饮 中午请客" """

    def test_basic(self):
        result = parse_message("128 餐饮 中午请客")
        assert result.amount == 128.0
        assert result.category == "餐饮"
        assert result.note == "中午请客"

    def test_decimal_amount(self):
        result = parse_message("36.5 交通 打车回家")
        assert result.amount == 36.5
        assert result.category == "交通"
        assert result.note == "打车回家"

    def test_two_decimal_places(self):
        result = parse_message("99.99 购物 日用品")
        assert result.amount == 99.99

    def test_chinese_category(self):
        result = parse_message("50 教育 书本费")
        assert result.amount == 50.0
        assert result.category == "教育"


KNOWN = {"餐饮", "交通", "购物", "教育", "医疗", "居住", "娱乐", "其他"}


class TestParseCategoryOnly:
    """Format 2: amount category → "36.5 交通" """

    def test_basic(self):
        result = parse_message("36.5 交通", known_categories=KNOWN)
        assert result.amount == 36.5
        assert result.category == "交通"
        assert result.note is None

    def test_integer_amount(self):
        result = parse_message("200 购物", known_categories=KNOWN)
        assert result.amount == 200.0
        assert result.note is None

    def test_small_amount(self):
        result = parse_message("0.5 餐饮", known_categories=KNOWN)
        assert result.amount == 0.5


class TestParseAmountNote:
    """Format 3: amount note → "32 早饭" (second token not in known_categories)"""

    def test_basic(self):
        result = parse_message("32 早饭")
        assert result.amount == 32.0
        assert result.category is None
        assert result.note == "早饭"

    def test_multi_word_note(self):
        result = parse_message("128 中午请客吃饭")
        assert result.amount == 128.0
        assert result.note == "中午请客吃饭"


class TestParseErrors:
    """Error handling for invalid input."""

    def test_empty_string(self):
        with pytest.raises(ParseError):
            parse_message("")

    def test_non_numeric(self):
        with pytest.raises(ParseError):
            parse_message("abc 餐饮")

    def test_amount_only(self):
        with pytest.raises(ParseError):
            parse_message("128")

    def test_very_long_input(self):
        with pytest.raises(ParseError):
            parse_message("x" * 1000)


class TestResolveCategory:
    def test_existing_category(self, repo, user_id):
        cat_id = resolve_category(repo, "餐饮", user_id)
        assert cat_id is not None
        assert cat_id > 0

    def test_none_falls_back_to_other(self, repo, user_id):
        cat_id = resolve_category(repo, None, user_id)
        cat = repo.fetch_one("SELECT name FROM categories WHERE id = ?", (cat_id,))
        assert cat["name"] == "其他"

    def test_unknown_creates_ad_hoc(self, repo, user_id):
        cat_id = resolve_category(repo, "宠物", user_id)
        assert cat_id > 0
        cat = repo.fetch_one("SELECT name FROM categories WHERE id = ?", (cat_id,))
        assert cat["name"] == "宠物"
