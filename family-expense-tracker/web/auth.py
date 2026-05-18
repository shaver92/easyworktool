from __future__ import annotations

import hashlib
import hmac as hmac_mod
import time
from typing import Any

import streamlit as st


def hash_pin(pin: str) -> str:
    """Hash a 4-digit PIN using SHA-256."""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verify_pin(pin_hash: str | None, pin: str) -> bool:
    """Constant-time PIN verification."""
    if not pin_hash:
        return False
    computed = hash_pin(pin)
    return hmac_mod.compare_digest(computed, pin_hash)


def check_rate_limit(user_id: int, max_attempts: int = 5) -> tuple[bool, int]:
    """Check if the user has exceeded PIN attempt limit with exponential backoff.

    Returns (is_blocked, wait_seconds).
    """
    key = f"pin_attempts_{user_id}"
    attempts = st.session_state.get(key, 0)
    if attempts >= max_attempts:
        wait = 2 ** attempts
        last_attempt = st.session_state.get(f"{key}_last", 0)
        elapsed = time.time() - last_attempt
        if elapsed < wait:
            return True, int(wait - elapsed)
        # Cool-down expired — reset
        st.session_state[key] = 0
        return False, 0
    return False, 0


def record_failed_attempt(user_id: int) -> None:
    """Record a failed PIN attempt and apply exponential backoff."""
    key = f"pin_attempts_{user_id}"
    st.session_state[key] = st.session_state.get(key, 0) + 1
    st.session_state[f"{key}_last"] = time.time()


def reset_attempts(user_id: int) -> None:
    """Reset PIN attempt counter on successful login."""
    st.session_state.pop(f"pin_attempts_{user_id}", None)
    st.session_state.pop(f"pin_attempts_{user_id}_last", None)


def build_oauth_url(cfg: dict) -> str:
    """Build the Feishu OAuth authorization URL."""
    feishu = cfg.get("feishu", {})
    app_id = feishu.get("app_id", "")
    redirect_uri = feishu.get("redirect_uri", "")
    if not app_id or not redirect_uri:
        return ""
    return (
        f"https://open.feishu.cn/open-apis/authen/v1/authorize"
        f"?app_id={app_id}"
        f"&redirect_uri={redirect_uri}"
    )


def resolve_feishu_user(cfg: dict) -> dict[str, Any] | None:
    """Resolve the current user from Feishu OAuth query params.

    Returns user dict or None if no OAuth code present.
    """
    qp = st.query_params
    code = qp.get("code")
    if not code:
        return None

    from bot.feishu_client import FeishuClient
    client = FeishuClient(cfg)
    try:
        tokens = client.get_oauth_tokens(code)
        user_access_token = tokens.get("access_token", "")
        if not user_access_token:
            return None
        user_info = client.get_user_info(user_access_token)
        open_id = user_info.get("open_id", "")
        name = user_info.get("name", "")
        if not open_id:
            return None

        from shared.database import Repository
        repo = Repository(cfg["app"]["db_path"])
        repo.init_schema()

        user = repo.fetch_one(
            "SELECT * FROM users WHERE feishu_open_id = ?",
            (open_id,),
        )
        if not user:
            is_admin = open_id in cfg.get("auth", {}).get("admin_open_ids", [])
            user_id = repo.execute(
                "INSERT INTO users (feishu_open_id, display_name, auth_method, is_admin) VALUES (?, ?, 'feishu_oauth', ?)",
                (open_id, name, int(is_admin)),
            )
            return {"id": user_id, "display_name": name, "feishu_open_id": open_id, "is_admin": is_admin, "auth_method": "feishu_oauth"}
        return dict(user)
    except Exception:
        return None


def resolve_pin_user(cfg: dict) -> dict[str, Any] | None:
    """Resolve the current user from Streamlit session state (PIN login)."""
    return st.session_state.get("user")


def is_admin(user: dict | None, cfg: dict) -> bool:
    if not user:
        return False
    if user.get("is_admin"):
        return True
    open_id = user.get("feishu_open_id", "")
    admin_ids = cfg.get("auth", {}).get("admin_open_ids", [])
    return open_id in admin_ids
