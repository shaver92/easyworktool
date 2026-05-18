from __future__ import annotations

import pytest
from shared.database import Repository


@pytest.fixture
def repo(tmp_path):
    r = Repository(str(tmp_path / "test_shared.db"))
    r.init_schema()
    return r


@pytest.fixture
def user_id(repo):
    return repo.execute(
        "INSERT INTO users (display_name, auth_method, web_pin_hash) VALUES ('爸爸', 'web_pin', 'hash123')"
    )


@pytest.fixture
def category_id(repo, user_id):
    return repo.execute(
        "INSERT INTO categories (name, icon, created_by) VALUES ('餐饮', '🍜', ?)",
        (user_id,),
    )


@pytest.fixture
def expense_id(repo, user_id, category_id):
    return repo.execute(
        "INSERT INTO expenses (user_id, category_id, amount, type, note, source) VALUES (?, ?, 128.0, 'expense', '午餐', 'web')",
        (user_id, category_id),
    )
