from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import logging

import tornado.web

from shared.config import load_config
from shared.database import Repository
from bot.parser import parse_message, resolve_category, ParseError, ParseTimeout

logger = logging.getLogger("family-expense-webhook")


class FeishuWebhookHandler(tornado.web.RequestHandler):
    """Tornado handler for Feishu event subscription callbacks."""

    def get(self):
        challenge = self.get_argument("challenge", None)
        if challenge:
            self.set_header("Content-Type", "text/plain")
            self.write(challenge)
        else:
            self.set_status(400, "Missing challenge")

    def post(self):
        cfg = load_config()
        feishu_cfg = cfg.get("feishu", {})

        body = self.request.body
        timestamp = self.request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = self.request.headers.get("X-Lark-Request-Nonce", "")
        signature = self.request.headers.get("X-Lark-Signature", "")

        token = feishu_cfg.get("verification_token", "")
        if token:
            sign_str = f"{timestamp}{nonce}{token}{body.decode('utf-8')}"
            computed = hashlib.sha256(sign_str.encode("utf-8")).hexdigest()
            if not hmac_mod.compare_digest(computed, signature):
                logger.warning("Webhook signature verification failed")
                self.set_status(401)
                self.write("Invalid signature")
                return

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.set_status(400)
            self.write("Invalid JSON")
            return

        challenge = payload.get("challenge")
        if challenge:
            self.set_header("Content-Type", "text/plain")
            self.write(challenge)
            return

        event = payload.get("event", {})
        event_type = payload.get("type") or event.get("type", "")

        if event_type == "im.message.receive_v1":
            self._process_message(event, payload.get("header", {}))
            self.write(json.dumps({"code": 0}))
        else:
            self.write(json.dumps({"code": 0}))

    def _process_message(self, event: dict, header: dict):
        cfg = load_config()
        repo = Repository(cfg["app"]["db_path"])
        repo.init_schema()

        message_id = header.get("event_id", "")
        if not message_id:
            return

        existing = repo.fetch_one(
            "SELECT id FROM expenses WHERE feishu_event_id = ?",
            (message_id,),
        )
        if existing:
            return

        message = event.get("message", {})
        content_str = message.get("content", "{}")
        try:
            content = json.loads(content_str)
        except json.JSONDecodeError:
            return
        text = content.get("text", "").strip()
        if not text:
            return

        sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")

        user = repo.fetch_one(
            "SELECT id, display_name FROM users WHERE feishu_open_id = ?",
            (sender_id,),
        )
        if not user:
            user_id = repo.execute(
                "INSERT INTO users (feishu_open_id, display_name, auth_method) VALUES (?, ?, 'feishu_oauth')",
                (sender_id, f"用户{sender_id[-4:]}"),
            )
            user = {"id": user_id}
        user_id = user["id"]

        cat_rows = repo.fetch_all("SELECT name FROM categories")
        known_categories = {r["name"] for r in cat_rows} if cat_rows else set()

        try:
            parsed = parse_message(text, known_categories=known_categories)
        except (ParseTimeout, ParseError):
            return

        category_id = resolve_category(repo, parsed.category, user_id)
        repo.execute(
            """INSERT INTO expenses (user_id, category_id, amount, type, note, source, feishu_event_id)
               VALUES (?, ?, ?, ?, ?, 'feishu_bot', ?)""",
            (user_id, category_id, parsed.amount, "expense", parsed.note or "", message_id),
        )


WEBHOOK_PATCH_OK = False
WEBHOOK_PATCH_ERROR = ""


def _find_tornado_app():
    """Find the running Tornado Application in the current process."""
    import gc
    from tornado.web import Application
    apps = [obj for obj in gc.get_objects() if isinstance(obj, Application)]
    return apps[0] if apps else None


def patch_streamlit_server() -> bool:
    """Add Feishu webhook route to Streamlit's internal Tornado server."""
    global WEBHOOK_PATCH_OK, WEBHOOK_PATCH_ERROR

    tornado_app = _find_tornado_app()
    if tornado_app is None:
        WEBHOOK_PATCH_ERROR = "No Tornado Application found in process"
        logger.warning(WEBHOOK_PATCH_ERROR)
        return False

    try:
        tornado_app.add_handlers(r".*$", [(r"/webhook", FeishuWebhookHandler)])
    except Exception as e:
        WEBHOOK_PATCH_ERROR = f"add_handlers error: {e}"
        logger.warning(WEBHOOK_PATCH_ERROR)
        return False

    WEBHOOK_PATCH_OK = True
    WEBHOOK_PATCH_ERROR = ""
    logger.info("Feishu webhook registered at /webhook")
    return True
