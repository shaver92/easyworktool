from __future__ import annotations

import json

from src.db.repository import Repository


class AuditService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def log(
        self,
        actor_open_id: str,
        action: str,
        target_type: str,
        target_id: str,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        self.repo.execute(
            """
            INSERT INTO audit_logs(actor_open_id, action, target_type, target_id, before_json, after_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                actor_open_id,
                action,
                target_type,
                target_id,
                json.dumps(before or {}, ensure_ascii=False),
                json.dumps(after or {}, ensure_ascii=False),
            ),
        )

    def list_logs(self, limit: int = 200) -> list[dict]:
        return self.repo.fetch_all(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    def list_logs_by_target(self, target_type: str, target_id: str, limit: int = 200) -> list[dict]:
        return self.repo.fetch_all(
            """
            SELECT * FROM audit_logs
            WHERE target_type = ? AND target_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (target_type, target_id, limit),
        )
