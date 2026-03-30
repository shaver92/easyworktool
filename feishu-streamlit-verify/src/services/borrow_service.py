from __future__ import annotations

from datetime import datetime

from src.db.repository import Repository


class BorrowService:
    def __init__(self, repo: Repository, require_approval: bool = False) -> None:
        self.repo = repo
        self.require_approval = require_approval

    def create_borrow_order(
        self,
        applicant_open_id: str,
        material_id: int,
        qty: int,
        due_at: str,
        note: str = "",
    ) -> int:
        material = self.repo.fetch_one("SELECT * FROM materials WHERE id = ?", (material_id,))
        if not material:
            raise ValueError("物资不存在")
        if material["status"] != "available":
            raise ValueError("该物资当前不可借")
        if material["available_qty"] < qty:
            raise ValueError("可借库存不足")

        order_no = f"BR-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        initial_status = "pending_approval" if self.require_approval else "borrowed"
        order_id = self.repo.execute(
            """
            INSERT INTO borrow_orders(order_no, applicant_open_id, due_at, note, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_no, applicant_open_id, due_at, note, initial_status),
        )
        self.repo.execute(
            "INSERT INTO borrow_items(borrow_order_id, material_id, qty, returned_qty) VALUES (?, ?, ?, 0)",
            (order_id, material_id, qty),
        )
        if not self.require_approval:
            self.repo.execute(
                "UPDATE materials SET available_qty = available_qty - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (qty, material_id),
            )
            self.repo.execute(
                """
                INSERT INTO inventory_transactions(material_id, action, qty_delta, reason, operator_open_id)
                VALUES (?, 'borrow_out', ?, ?, ?)
                """,
                (material_id, -qty, note, applicant_open_id),
            )
        return order_id

    def approve_order(self, order_id: int, approver_open_id: str) -> None:
        order = self.repo.fetch_one("SELECT * FROM borrow_orders WHERE id = ?", (order_id,))
        if not order:
            raise ValueError("借用单不存在")
        if order["status"] != "pending_approval":
            raise ValueError("该借用单当前不可审批")
        item = self.repo.fetch_one("SELECT * FROM borrow_items WHERE borrow_order_id = ?", (order_id,))
        if not item:
            raise ValueError("借用单明细不存在")
        material = self.repo.fetch_one("SELECT * FROM materials WHERE id = ?", (item["material_id"],))
        if not material or material["available_qty"] < item["qty"]:
            raise ValueError("审批失败：库存不足")
        self.repo.execute(
            "UPDATE materials SET available_qty = available_qty - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (item["qty"], item["material_id"]),
        )
        self.repo.execute(
            """
            UPDATE borrow_orders
            SET status = 'borrowed', approver_open_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (approver_open_id, order_id),
        )
        self.repo.execute(
            """
            INSERT INTO inventory_transactions(material_id, action, qty_delta, reason, operator_open_id)
            VALUES (?, 'borrow_out', ?, '审批通过出库', ?)
            """,
            (item["material_id"], -item["qty"], approver_open_id),
        )

    def reject_order(self, order_id: int, approver_open_id: str, reason: str = "") -> None:
        order = self.repo.fetch_one("SELECT * FROM borrow_orders WHERE id = ?", (order_id,))
        if not order:
            raise ValueError("借用单不存在")
        if order["status"] != "pending_approval":
            raise ValueError("该借用单当前不可驳回")
        self.repo.execute(
            """
            UPDATE borrow_orders
            SET status = 'rejected', approver_open_id = ?, note = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (approver_open_id, reason or order.get("note", ""), order_id),
        )

    def return_order(self, order_id: int, operator_open_id: str) -> None:
        self.return_order_partial(order_id, operator_open_id, return_qty=None)

    def return_order_partial(self, order_id: int, operator_open_id: str, return_qty: int | None) -> None:
        order = self.repo.fetch_one("SELECT * FROM borrow_orders WHERE id = ?", (order_id,))
        if not order:
            raise ValueError("借用单不存在")
        if order["status"] == "returned":
            return
        if order["status"] not in {"borrowed", "partially_returned"}:
            raise ValueError("当前状态不允许归还")
        item = self.repo.fetch_one("SELECT * FROM borrow_items WHERE borrow_order_id = ?", (order_id,))
        if not item:
            raise ValueError("借用单明细不存在")
        remaining_qty = item["qty"] - item.get("returned_qty", 0)
        if remaining_qty <= 0:
            return
        qty_to_return = remaining_qty if return_qty is None else return_qty
        if qty_to_return <= 0:
            raise ValueError("归还数量必须大于 0")
        if qty_to_return > remaining_qty:
            raise ValueError("归还数量超过未归还数量")

        self.repo.execute(
            "UPDATE materials SET available_qty = available_qty + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (qty_to_return, item["material_id"]),
        )
        new_returned_qty = item.get("returned_qty", 0) + qty_to_return
        new_status = "returned" if new_returned_qty >= item["qty"] else "partially_returned"
        returned_at_sql = ", returned_at = CURRENT_TIMESTAMP" if new_status == "returned" else ""
        self.repo.execute(
            """
            UPDATE borrow_orders
            SET status = ?, approver_open_id = ?, updated_at = CURRENT_TIMESTAMP
            """ + returned_at_sql + """
            WHERE id = ?
            """,
            (new_status, operator_open_id, order_id),
        )
        self.repo.execute(
            """
            UPDATE borrow_items
            SET returned_qty = ?
            WHERE borrow_order_id = ?
            """,
            (new_returned_qty, order_id),
        )
        self.repo.execute(
            """
            INSERT INTO inventory_transactions(material_id, action, qty_delta, reason, operator_open_id)
            VALUES (?, 'return_in', ?, '归还入库', ?)
            """,
            (item["material_id"], qty_to_return, operator_open_id),
        )

    def list_orders(self, applicant_open_id: str | None = None) -> list[dict]:
        base_sql = """
            SELECT bo.*, bi.material_id, bi.qty, bi.returned_qty, (bi.qty - bi.returned_qty) AS remaining_qty,
                   m.name AS material_name, m.code AS material_code
            FROM borrow_orders bo
            JOIN borrow_items bi ON bo.id = bi.borrow_order_id
            JOIN materials m ON m.id = bi.material_id
        """
        if applicant_open_id:
            return self.repo.fetch_all(
                base_sql + " WHERE bo.applicant_open_id = ? ORDER BY bo.id DESC",
                (applicant_open_id,),
            )
        return self.repo.fetch_all(base_sql + " ORDER BY bo.id DESC")

    def list_due_and_overdue(self, days_before_due: int) -> list[dict]:
        return self.repo.fetch_all(
            """
            SELECT bo.*, bi.material_id, bi.qty, bi.returned_qty, (bi.qty - bi.returned_qty) AS remaining_qty,
                   m.name AS material_name
            FROM borrow_orders bo
            JOIN borrow_items bi ON bo.id = bi.borrow_order_id
            JOIN materials m ON m.id = bi.material_id
            WHERE bo.status IN ('borrowed', 'partially_returned')
              AND date(bo.due_at) <= date('now', '+' || ? || ' day')
            ORDER BY bo.due_at ASC
            """,
            (days_before_due,),
        )

    def get_order_detail(self, order_id: int) -> dict | None:
        return self.repo.fetch_one(
            """
            SELECT bo.*, bi.material_id, bi.qty, bi.returned_qty, (bi.qty - bi.returned_qty) AS remaining_qty,
                   m.name AS material_name, m.code AS material_code
            FROM borrow_orders bo
            JOIN borrow_items bi ON bo.id = bi.borrow_order_id
            JOIN materials m ON m.id = bi.material_id
            WHERE bo.id = ?
            """,
            (order_id,),
        )
