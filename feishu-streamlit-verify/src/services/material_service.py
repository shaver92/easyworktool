from __future__ import annotations

from src.db.repository import Repository


class MaterialService:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def seed_demo_if_empty(self) -> None:
        cnt = self.repo.fetch_one("SELECT COUNT(*) AS c FROM materials WHERE is_deleted = 0")
        if cnt and cnt["c"] > 0:
            return
        self.repo.execute_many(
            """
            INSERT INTO materials(code, name, category, spec, location, total_qty, available_qty, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("NB-001", "笔记本电脑", "电子设备", "i5/16G/512G", "A区-设备柜", 8, 5, "available"),
                ("PR-001", "投影仪", "会议设备", "1080P", "B区-会议室", 2, 2, "available"),
                ("TL-001", "扭力扳手", "工具", "10-60N.m", "C区-工具间", 10, 9, "available"),
            ],
        )

    def list_materials(self, include_off_shelf: bool = True) -> list[dict]:
        if include_off_shelf:
            return self.repo.fetch_all(
                "SELECT * FROM materials WHERE is_deleted = 0 ORDER BY id DESC"
            )
        return self.repo.fetch_all(
            "SELECT * FROM materials WHERE is_deleted = 0 AND status = 'available' ORDER BY id DESC"
        )

    def add_material(self, payload: dict) -> int:
        return self.repo.execute(
            """
            INSERT INTO materials(code, name, category, spec, location, owner_open_id, total_qty, available_qty, status, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["code"],
                payload["name"],
                payload["category"],
                payload.get("spec", ""),
                payload.get("location", ""),
                payload.get("owner_open_id"),
                payload["total_qty"],
                payload["available_qty"],
                payload.get("status", "available"),
                payload.get("image_url", ""),
            ),
        )

    def update_status(self, material_id: int, status: str) -> None:
        self.repo.execute(
            "UPDATE materials SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, material_id),
        )

    def adjust_inventory(self, material_id: int, delta: int) -> None:
        current = self.repo.fetch_one("SELECT * FROM materials WHERE id = ?", (material_id,))
        if not current:
            raise ValueError("物资不存在")
        total_qty = current["total_qty"] + delta
        available_qty = current["available_qty"] + delta
        if total_qty < 0 or available_qty < 0:
            raise ValueError("调整后库存不能小于 0")
        self.repo.execute(
            "UPDATE materials SET total_qty = ?, available_qty = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (total_qty, available_qty, material_id),
        )

    def get_material(self, material_id: int) -> dict | None:
        return self.repo.fetch_one("SELECT * FROM materials WHERE id = ?", (material_id,))
