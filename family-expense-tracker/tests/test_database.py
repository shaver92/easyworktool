from __future__ import annotations

import pytest
from shared.database import Repository


class TestSchemaInit:
    def test_tables_created(self, repo):
        tables = repo.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = {t["name"] for t in tables}
        assert "users" in table_names
        assert "categories" in table_names
        assert "expenses" in table_names
        assert "budgets" in table_names

    def test_wal_enabled(self, tmp_path):
        from shared.database import Repository
        repo = Repository(str(tmp_path / "test_wal.db"))
        repo.init_schema()
        row = repo.fetch_one("PRAGMA journal_mode")
        assert row["journal_mode"] == "wal"

    def test_foreign_keys_on(self, repo):
        row = repo.fetch_one("PRAGMA foreign_keys")
        assert row["foreign_keys"] == 1


class TestCRUD:
    def test_insert_user(self, repo):
        uid = repo.execute(
            "INSERT INTO users (display_name, auth_method) VALUES ('测试', 'web_pin')"
        )
        assert uid > 0
        user = repo.fetch_one("SELECT * FROM users WHERE id = ?", (uid,))
        assert user["display_name"] == "测试"

    def test_insert_expense(self, repo, user_id, category_id):
        eid = repo.execute(
            "INSERT INTO expenses (user_id, category_id, amount, type, note, source) VALUES (?, ?, 100.0, 'expense', '测试', 'web')",
            (user_id, category_id),
        )
        assert eid > 0
        exp = repo.fetch_one("SELECT * FROM expenses WHERE id = ?", (eid,))
        assert exp["amount"] == 100.0

    def test_insert_budget(self, repo, user_id):
        bid = repo.execute(
            "INSERT INTO budgets (user_id, amount, month, warn_threshold) VALUES (?, 5000, '2026-05', 0.8)",
            (user_id,),
        )
        assert bid > 0

    def test_fk_enforcement(self, repo):
        """Foreign key should reject invalid references."""
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            repo.execute(
                "INSERT INTO expenses (user_id, category_id, amount) VALUES (99999, 99999, 100)"
            )

    def test_transaction(self, repo):
        repo.transaction([
            ("INSERT INTO users (display_name, auth_method) VALUES ('multi_a', 'web_pin')", ()),
            ("INSERT INTO users (display_name, auth_method) VALUES ('multi_b', 'web_pin')", ()),
        ])
        count = repo.fetch_scalar("SELECT COUNT(*) FROM users")
        assert count >= 2  # includes fixture users


class TestSystemCategories:
    def test_system_categories_seeded(self, repo):
        cats = repo.fetch_all("SELECT name FROM categories WHERE is_system = 1")
        names = {c["name"] for c in cats}
        assert "餐饮" in names
        assert "交通" in names
        assert "购物" in names
