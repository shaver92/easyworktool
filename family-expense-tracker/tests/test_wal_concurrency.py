from __future__ import annotations

import threading
import pytest
from shared.database import Repository


class TestWALConcurrency:
    def test_concurrent_read_write(self, tmp_path):
        """Write expenses in one thread while reading dashboard aggregates in another."""
        db_path = str(tmp_path / "test_concurrent.db")
        repo = Repository(db_path)
        repo.init_schema()

        uid = repo.execute("INSERT INTO users (display_name, auth_method) VALUES ('测试', 'web_pin')")
        cat_id = repo.fetch_one("SELECT id FROM categories WHERE name = '餐饮'")["id"]

        errors = []

        def writer():
            try:
                w = Repository(db_path)
                for i in range(50):
                    w.execute(
                        "INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, ?, 'expense', 'web')",
                        (uid, cat_id, 10.0 + i),
                    )
            except Exception as exc:
                errors.append(("writer", str(exc)))

        def reader():
            try:
                r = Repository(db_path)
                for _ in range(50):
                    result = r.fetch_one("SELECT COUNT(*) AS c FROM expenses")
                    # Just verify we get a consistent result
                    assert result is not None
            except Exception as exc:
                errors.append(("reader", str(exc)))

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Concurrency errors: {errors}"

        # Verify all writes landed
        count = repo.fetch_scalar("SELECT COUNT(*) FROM expenses")
        assert count == 50
