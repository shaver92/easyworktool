from __future__ import annotations

from pathlib import Path
import os
import tomllib
import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "app_config.toml"


def load_config() -> dict:
    load_dotenv(ROOT_DIR / ".env")
    with CONFIG_PATH.open("rb") as f:
        cfg = tomllib.load(f)
    return _apply_env_overrides(cfg)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _get_list(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _apply_env_overrides(cfg: dict) -> dict:
    cfg["app"]["name"] = os.getenv("APP_NAME", cfg["app"].get("name", "飞书物资管理系统"))
    cfg["app"]["db_path"] = os.getenv("APP_DB_PATH", cfg["app"].get("db_path", "data/materials.db"))
    cfg["app"]["timezone"] = os.getenv("APP_TIMEZONE", cfg["app"].get("timezone", "Asia/Shanghai"))
    cfg["app"]["home_url"] = os.getenv("APP_HOME_URL", cfg["app"].get("home_url", "http://localhost:8501"))
    cfg["app"]["require_borrow_approval"] = _get_bool(
        "APP_REQUIRE_BORROW_APPROVAL",
        cfg["app"].get("require_borrow_approval", False),
    )

    cfg["feishu"]["app_id"] = os.getenv("FEISHU_APP_ID", cfg["feishu"].get("app_id", ""))
    cfg["feishu"]["app_secret"] = os.getenv("FEISHU_APP_SECRET", cfg["feishu"].get("app_secret", ""))
    cfg["feishu"]["tenant_access_token"] = os.getenv(
        "FEISHU_TENANT_ACCESS_TOKEN",
        cfg["feishu"].get("tenant_access_token", ""),
    )
    cfg["feishu"]["base_url"] = os.getenv("FEISHU_BASE_URL", cfg["feishu"].get("base_url", ""))
    cfg["feishu"]["redirect_uri"] = os.getenv("FEISHU_REDIRECT_URI", cfg["feishu"].get("redirect_uri", ""))

    cfg["rbac"]["admin_open_ids"] = _get_list("RBAC_ADMIN_OPEN_IDS", cfg["rbac"].get("admin_open_ids", []))
    cfg["rbac"]["admin_emails"] = _get_list("RBAC_ADMIN_EMAILS", cfg["rbac"].get("admin_emails", []))

    cfg["notify"]["enable"] = _get_bool("NOTIFY_ENABLE", cfg["notify"].get("enable", False))
    cfg["notify"]["days_before_due"] = _get_int("NOTIFY_DAYS_BEFORE_DUE", cfg["notify"].get("days_before_due", 3))
    cfg["notify"]["overdue_every_hours"] = _get_int(
        "NOTIFY_OVERDUE_EVERY_HOURS",
        cfg["notify"].get("overdue_every_hours", 24),
    )
    cfg["notify"]["retry_limit"] = _get_int("NOTIFY_RETRY_LIMIT", cfg["notify"].get("retry_limit", 3))
    cfg["notify"]["due_template"] = os.getenv("NOTIFY_DUE_TEMPLATE", cfg["notify"].get("due_template", ""))
    cfg["notify"]["overdue_template"] = os.getenv("NOTIFY_OVERDUE_TEMPLATE", cfg["notify"].get("overdue_template", ""))
    cfg["notify"]["manual_template"] = os.getenv("NOTIFY_MANUAL_TEMPLATE", cfg["notify"].get("manual_template", ""))
    cfg["notify"]["admin_cc_open_ids"] = _get_list(
        "NOTIFY_ADMIN_CC_OPEN_IDS",
        cfg["notify"].get("admin_cc_open_ids", []),
    )
    cfg["notify"]["use_template_card"] = _get_bool(
        "NOTIFY_USE_TEMPLATE_CARD",
        cfg["notify"].get("use_template_card", False),
    )
    _auto_fill_feishu_token(cfg)
    return cfg


def _auto_fill_feishu_token(cfg: dict) -> None:
    feishu_cfg = cfg.get("feishu", {})
    if feishu_cfg.get("tenant_access_token"):
        return
    app_id = feishu_cfg.get("app_id", "")
    app_secret = feishu_cfg.get("app_secret", "")
    base_url = feishu_cfg.get("base_url", "")
    if not (app_id and app_secret and base_url):
        return
    try:
        resp = requests.post(
            f"{base_url}/auth/v3/app_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=8,
        )
        if not resp.ok:
            return
        payload = resp.json()
        token = payload.get("tenant_access_token", "")
        if token:
            cfg["feishu"]["tenant_access_token"] = token
    except requests.RequestException:
        return


def validate_config(cfg: dict) -> list[str]:
    warnings: list[str] = []
    if cfg["notify"].get("enable", False) and not cfg["feishu"].get("tenant_access_token"):
        warnings.append("已启用通知，但无法自动获取 tenant_access_token，请检查 FEISHU_APP_ID/FEISHU_APP_SECRET。")
    if not cfg["rbac"].get("admin_open_ids"):
        warnings.append("未配置 RBAC_ADMIN_OPEN_IDS，当前将无法识别管理员。")
    if cfg["app"].get("require_borrow_approval", False) and not cfg["rbac"].get("admin_open_ids"):
        warnings.append("已开启审批流，但未配置管理员，借用单将无法审批。")
    if not cfg["app"].get("home_url"):
        warnings.append("APP_HOME_URL 未配置，消息卡片跳转地址可能不正确。")
    if not cfg["feishu"].get("app_id") or not cfg["feishu"].get("app_secret"):
        warnings.append("FEISHU_APP_ID / FEISHU_APP_SECRET 未完整配置，OAuth code 登录不可用。")
    return warnings
