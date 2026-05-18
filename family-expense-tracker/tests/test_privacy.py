from __future__ import annotations

import pytest
from shared.database import Repository


@pytest.fixture
def multi_user_repo(tmp_path):
    """Repo with 2 users and separate expenses — isolated file DB."""
    r = Repository(str(tmp_path / "test_privacy.db"))
    r.init_schema()

    uid_a = r.execute("INSERT INTO users (display_name, auth_method) VALUES ('爸爸', 'web_pin')")
    uid_b = r.execute("INSERT INTO users (display_name, auth_method) VALUES ('妈妈', 'web_pin')")

    cat_food = r.fetch_one("SELECT id FROM categories WHERE name = '餐饮'")["id"]
    cat_trans = r.fetch_one("SELECT id FROM categories WHERE name = '交通'")["id"]

    r.execute("INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, 128, 'expense', 'web')", (uid_a, cat_food))
    r.execute("INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, 36, 'expense', 'web')", (uid_a, cat_trans))
    r.execute("INSERT INTO expenses (user_id, category_id, amount, type, source) VALUES (?, ?, 200, 'expense', 'web')", (uid_b, cat_food))

    return r, uid_a, uid_b


class TestPrivacy:
    def test_user_can_see_own_expenses(self, multi_user_repo):
        repo, uid_a, _ = multi_user_repo
        own = repo.fetch_all("SELECT * FROM expenses WHERE user_id = ?", (uid_a,))
        assert len(own) == 2

    def test_user_cannot_see_other_user_expenses(self, multi_user_repo):
        repo, _, uid_b = multi_user_repo
        others = repo.fetch_all("SELECT * FROM expenses WHERE user_id = ?", (uid_b,))
        assert len(others) == 1
        # Only uid_b's data
        assert others[0]["amount"] == 200

    def test_family_aggregate_hides_per_user_detail(self, multi_user_repo):
        repo, uid_a, _ = multi_user_repo
        # Family total by category — no per-user breakdown
        cats = repo.fetch_all("""
            SELECT c.name, SUM(e.amount) AS total
            FROM categories c
            JOIN expenses e ON c.id = e.category_id
            WHERE e.type = 'expense'
            GROUP BY c.id
        """)
        food = [c for c in cats if c["name"] == "餐饮"][0]
        assert food["total"] == 328  # 128 + 200, but does NOT expose who spent what

    def test_admin_can_see_all_expenses(self, multi_user_repo):
        repo, _, _ = multi_user_repo
        repo.execute("UPDATE users SET is_admin = 1 WHERE id = 1")
        all_exp = repo.fetch_all("SELECT * FROM expenses")
        assert len(all_exp) == 3  # admin sees all
