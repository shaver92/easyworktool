from __future__ import annotations

import pytest
from shared.database import Repository


class TestEmptyDashboard:
    def test_empty_weekly_summary(self, tmp_path):
        from web.charts import weekly_summary
        repo = Repository(str(tmp_path / "test_empty.db"))
        repo.init_schema()
        result = weekly_summary(repo)
        assert result["total"] == 0
        assert result["count"] == 0
        assert isinstance(result["categories"], list)
        assert isinstance(result["daily"], list)

    def test_empty_monthly_summary(self, tmp_path):
        from web.charts import monthly_summary
        repo = Repository(str(tmp_path / "test_empty.db"))
        repo.init_schema()
        result = monthly_summary(repo, 2026, 5)
        assert result["total"] == 0
        assert result["count"] == 0

    def test_empty_yearly_summary(self, tmp_path):
        from web.charts import yearly_summary
        repo = Repository(str(tmp_path / "test_empty.db"))
        repo.init_schema()
        result = yearly_summary(repo, 2026)
        assert result["total"] == 0
        assert result["count"] == 0

    def test_budget_not_set_returns_none(self, tmp_path):
        from web.charts import budget_status
        repo = Repository(str(tmp_path / "test_empty.db"))
        repo.init_schema()
        result = budget_status(repo, user_id=1, month="2026-05")
        assert result is None
