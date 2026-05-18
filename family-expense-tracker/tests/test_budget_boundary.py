from __future__ import annotations

import pytest
from shared.database import Repository
from web.charts import budget_status


class TestBudgetBoundary:
    @pytest.fixture
    def b_repo(self, tmp_path):
        r = Repository(str(tmp_path / "test_budget.db"))
        r.init_schema()
        uid = r.execute("INSERT INTO users (display_name, auth_method) VALUES ('测试', 'web_pin')")
        cat_id = r.fetch_one("SELECT id FROM categories WHERE name = '餐饮'")["id"]
        return r, uid, cat_id

    def test_zero_budget_no_division_error(self, b_repo):
        """Budget amount is 0 (shouldn't happen with CHECK constraint, but safety)."""
        repo, uid, _ = b_repo
        repo.execute("INSERT INTO budgets (user_id, amount, month, warn_threshold) VALUES (?, 5000, '2026-05', 0.8)", (uid,))
        result = budget_status(repo, uid, "2026-05")
        assert result["ratio"] == 0.0
        assert result["over_threshold"] is False

    def test_under_threshold_no_alert(self, b_repo):
        repo, uid, cat_id = b_repo
        repo.execute("INSERT INTO budgets (user_id, amount, month, warn_threshold) VALUES (?, 5000, '2026-05', 0.8)", (uid,))
        repo.execute("INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, 1000, 'expense', 'web')", (uid, cat_id))
        result = budget_status(repo, uid, "2026-05")
        assert result["ratio"] == 0.2
        assert result["over_threshold"] is False

    def test_at_80_percent_triggers_warning(self, b_repo):
        repo, uid, cat_id = b_repo
        repo.execute("INSERT INTO budgets (user_id, amount, month, warn_threshold) VALUES (?, 5000, '2026-05', 0.8)", (uid,))
        repo.execute("INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, 4000, 'expense', 'web')", (uid, cat_id))
        result = budget_status(repo, uid, "2026-05")
        assert result["ratio"] == 0.8
        assert result["over_threshold"] is True
        assert result["over_budget"] is False

    def test_at_79_9_percent_no_warning(self, b_repo):
        repo, uid, cat_id = b_repo
        repo.execute("INSERT INTO budgets (user_id, amount, month, warn_threshold) VALUES (?, 5000, '2026-05', 0.8)", (uid,))
        repo.execute("INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, 3995, 'expense', 'web')", (uid, cat_id))
        result = budget_status(repo, uid, "2026-05")
        assert result["ratio"] == pytest.approx(0.799)
        assert result["over_threshold"] is False

    def test_over_budget(self, b_repo):
        repo, uid, cat_id = b_repo
        repo.execute("INSERT INTO budgets (user_id, amount, month, warn_threshold) VALUES (?, 5000, '2026-05', 0.8)", (uid,))
        repo.execute("INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, 6000, 'expense', 'web')", (uid, cat_id))
        result = budget_status(repo, uid, "2026-05")
        assert result["ratio"] == 1.2
        assert result["over_budget"] is True
