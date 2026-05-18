from __future__ import annotations

import os
import tomllib
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.toml"


def load_config() -> dict:
    load_dotenv(ROOT_DIR / ".env")
    cfg = {}
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("rb") as f:
            cfg = tomllib.load(f)
    return _apply_env_overrides(cfg)


def _apply_env_overrides(cfg: dict) -> dict:
    app = cfg.setdefault("app", {})
    app["name"] = os.getenv("APP_NAME", app.get("name", "家庭记账"))
    app["db_path"] = os.getenv("APP_DB_PATH", app.get("db_path", "data/family_expenses.db"))
    app["timezone"] = os.getenv("APP_TIMEZONE", app.get("timezone", "Asia/Shanghai"))
    app["bot_port"] = int(os.getenv("BOT_PORT", str(app.get("bot_port", 8000))))
    app["web_port"] = int(os.getenv("WEB_PORT", str(app.get("web_port", 8501))))

    feishu = cfg.setdefault("feishu", {})
    feishu["app_id"] = os.getenv("FEISHU_APP_ID", feishu.get("app_id", ""))
    feishu["app_secret"] = os.getenv("FEISHU_APP_SECRET", feishu.get("app_secret", ""))
    feishu["verification_token"] = os.getenv("FEISHU_VERIFICATION_TOKEN", feishu.get("verification_token", ""))
    feishu["webhook_path"] = os.getenv("FEISHU_WEBHOOK_PATH", feishu.get("webhook_path", "/webhook"))
    feishu["redirect_uri"] = os.getenv("FEISHU_REDIRECT_URI", feishu.get("redirect_uri", ""))

    auth = cfg.setdefault("auth", {})
    auth["admin_open_ids"] = [x.strip() for x in os.getenv("AUTH_ADMIN_OPEN_IDS", "").split(",") if x.strip()] or auth.get("admin_open_ids", [])
    auth["pin_max_attempts"] = int(os.getenv("AUTH_PIN_MAX_ATTEMPTS", str(auth.get("pin_max_attempts", 5))))

    return cfg


def validate_config(cfg: dict) -> list[str]:
    warnings: list[str] = []
    feishu = cfg.get("feishu", {})
    if not feishu.get("app_id") or not feishu.get("app_secret"):
        warnings.append("FEISHU_APP_ID / FEISHU_APP_SECRET 未配置，飞书 Bot 和 OAuth 登录不可用。")
    if not feishu.get("verification_token"):
        warnings.append("FEISHU_VERIFICATION_TOKEN 未配置，飞书事件订阅签名验证将失败。")
    return warnings
