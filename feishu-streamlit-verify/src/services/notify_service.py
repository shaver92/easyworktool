from __future__ import annotations

from datetime import datetime
import json
from urllib.parse import urlencode
import requests

from src.db.repository import Repository


class NotifyService:
    def __init__(self, repo: Repository, cfg: dict) -> None:
        self.repo = repo
        self.cfg = cfg

    def _create_if_not_exists(self, order_id: int, receiver_open_id: str, notify_type: str, dedupe_key: str) -> bool:
        existed = self.repo.fetch_one("SELECT id FROM notifications WHERE dedupe_key = ?", (dedupe_key,))
        if existed:
            return False
        self.repo.execute(
            """
            INSERT INTO notifications(borrow_order_id, receiver_open_id, notify_type, dedupe_key, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (order_id, receiver_open_id, notify_type, dedupe_key),
        )
        return True

    def enqueue_due_notice(self, order: dict, notify_type: str) -> None:
        day = datetime.now().strftime("%Y-%m-%d")
        dedupe_key = f"{notify_type}:{order['id']}:{day}:owner"
        self._create_if_not_exists(order["id"], order["applicant_open_id"], notify_type, dedupe_key)
        if notify_type == "overdue":
            for admin_open_id in self.cfg.get("notify", {}).get("admin_cc_open_ids", []):
                admin_key = f"{notify_type}:{order['id']}:{day}:admin:{admin_open_id}"
                self._create_if_not_exists(order["id"], admin_open_id, "overdue_admin_cc", admin_key)

    def enqueue_manual_notice(self, order: dict, sender_open_id: str) -> None:
        minute = datetime.now().strftime("%Y-%m-%d-%H-%M")
        dedupe_key = f"manual:{order['id']}:{sender_open_id}:{minute}"
        self._create_if_not_exists(order["id"], order["applicant_open_id"], "manual_remind", dedupe_key)

    def dispatch_pending(self) -> None:
        pending = self.repo.fetch_all(
            """
            SELECT * FROM notifications
            WHERE status = 'pending' AND retry_count < ?
            ORDER BY id ASC
            """,
            (self.cfg["notify"].get("retry_limit", 3),),
        )
        for item in pending:
            ok, err = self._send_to_feishu(item)
            if ok:
                self.repo.execute(
                    "UPDATE notifications SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (item["id"],),
                )
            else:
                self.repo.execute(
                    """
                    UPDATE notifications
                    SET retry_count = retry_count + 1, last_error = ?
                    WHERE id = ?
                    """,
                    (err, item["id"]),
                )

    def list_notifications(self, limit: int = 200) -> list[dict]:
        return self.repo.fetch_all("SELECT * FROM notifications ORDER BY id DESC LIMIT ?", (limit,))

    def list_notifications_by_order(self, order_id: int, limit: int = 200) -> list[dict]:
        return self.repo.fetch_all(
            """
            SELECT * FROM notifications
            WHERE borrow_order_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (order_id, limit),
        )

    def _send_to_feishu(self, item: dict) -> tuple[bool, str]:
        if not self.cfg.get("notify", {}).get("enable", False):
            return True, ""
        token = self.cfg.get("feishu", {}).get("tenant_access_token", "")
        if not token:
            return False, "missing tenant_access_token"
        url = f"{self.cfg['feishu']['base_url']}/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        payload = self._build_payload(item)
        try:
            r = requests.post(url, headers=headers, params={"receive_id_type": "open_id"}, json=payload, timeout=8)
            if r.ok:
                return True, ""
            return False, f"http_{r.status_code}"
        except requests.RequestException as ex:
            return False, str(ex)

    def _build_payload(self, item: dict) -> dict:
        return {
            "receive_id": item["receiver_open_id"],
            "msg_type": "interactive",
            "content": self._build_card_content(item),
        }

    def _build_card_content(self, item: dict) -> str:
        notify_cfg = self.cfg.get("notify", {})
        if item["notify_type"] in {"overdue", "overdue_admin_cc"}:
            text = notify_cfg.get("overdue_template", "【逾期提醒】你有一条逾期借用记录，请及时归还。")
        elif item["notify_type"] == "manual_remind":
            text = notify_cfg.get("manual_template", "【催还提醒】管理员提醒你尽快归还。")
        else:
            text = notify_cfg.get("due_template", "【到期提醒】你有一条借用记录即将到期，请及时归还。")
        order = self.repo.fetch_one(
            "SELECT order_no, due_at FROM borrow_orders WHERE id = ?",
            (item["borrow_order_id"],),
        )
        order_no = order["order_no"] if order else "-"
        due_at = order["due_at"] if order else "-"
        if item["notify_type"] in {"overdue", "overdue_admin_cc"}:
            title = "物资逾期提醒"
        elif item["notify_type"] == "manual_remind":
            title = "物资催还提醒"
        else:
            title = "物资到期提醒"
        app_home = self.cfg.get("app", {}).get("home_url", "http://localhost:8501")
        app_link = f"{app_home}?{urlencode({'page': '借用单详情', 'order_id': item['borrow_order_id']})}"
        card = {
            "type": "template",
            "data": {
                "template_id": "AAqXnNfM6xQwM",
                "template_variable": {
                    "title": title,
                    "message": text,
                    "order_no": order_no,
                    "due_at": due_at,
                    "app_home": app_link,
                },
            },
        }
        # Fallback plain card when template_id is unavailable or invalid in tenant.
        if not self.cfg.get("notify", {}).get("use_template_card", False):
            card = {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": title}},
                "elements": [
                    {"tag": "markdown", "content": text},
                    {
                        "tag": "markdown",
                        "content": f"借用单号: {order_no}\n应还日期: {due_at}",
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "打开系统处理"},
                                "type": "primary",
                                "url": app_link,
                            }
                        ],
                    },
                ],
            }
        return json.dumps(card, ensure_ascii=False)
