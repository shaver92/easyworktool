from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from src.config import ROOT_DIR


class Repository:
    def __init__(self, db_path: str) -> None:
        full_path = ROOT_DIR / db_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(full_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_schema(self) -> None:
        schema_path = ROOT_DIR / "src" / "db" / "schema.sql"
        sql = schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(sql)
            # Lightweight migration for old DB files.
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(borrow_items)").fetchall()
            }
            if "returned_qty" not in columns:
                conn.execute(
                    "ALTER TABLE borrow_items ADD COLUMN returned_qty INTEGER NOT NULL DEFAULT 0"
                )
            conn.commit()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self._connect() as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid

    def execute_many(self, sql: str, params_seq: list[tuple[Any, ...]]) -> None:
        with self._connect() as conn:
            conn.executemany(sql, params_seq)
            conn.commit()

    def fetch_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def transaction(self, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
        with self._connect() as conn:
            for sql, params in statements:
                conn.execute(sql, params)
            conn.commit()
