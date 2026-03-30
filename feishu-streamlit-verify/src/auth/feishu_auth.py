from __future__ import annotations

import requests
import streamlit as st


def _safe_get_json(url: str, headers: dict | None = None, params: dict | None = None) -> dict:
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=8)
        if resp.ok:
            return resp.json()
    except requests.RequestException:
        return {}
    return {}


def _safe_post_json(url: str, payload: dict, headers: dict | None = None) -> dict:
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=8)
        if resp.ok:
            return resp.json()
    except requests.RequestException:
        return {}
    return {}


def _fetch_user_by_access_token(base_url: str, user_access_token: str) -> dict:
    url = f"{base_url}/authen/v1/user_info"
    payload = _safe_get_json(url, headers={"Authorization": f"Bearer {user_access_token}"})
    return payload.get("data", {})


def _exchange_code_for_user(config: dict, code: str) -> dict:
    feishu_cfg = config.get("feishu", {})
    base_url = feishu_cfg.get("base_url", "")
    app_id = feishu_cfg.get("app_id", "")
    app_secret = feishu_cfg.get("app_secret", "")
    if not (base_url and app_id and app_secret):
        return {}

    app_token_payload = _safe_post_json(
        f"{base_url}/auth/v3/app_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    app_access_token = app_token_payload.get("app_access_token", "")
    if not app_access_token:
        return {}

    oauth_payload = _safe_post_json(
        f"{base_url}/authen/v2/oauth/token",
        {"grant_type": "authorization_code", "code": code},
        headers={"Authorization": f"Bearer {app_access_token}"},
    )
    data = oauth_payload.get("data", {})
    user_access_token = data.get("access_token", "")
    if not user_access_token:
        return {}
    return _fetch_user_by_access_token(base_url, user_access_token)


def resolve_user(config: dict) -> dict:
    qp = st.query_params
    open_id = qp.get("open_id")
    name = qp.get("name")
    email = qp.get("email")
    if open_id:
        return {
            "open_id": str(open_id),
            "name": str(name or "FeishuUser"),
            "email": str(email or ""),
            "source": "query_params",
        }

    feishu_cfg = config.get("feishu", {})
    code = qp.get("code")
    if code:
        data = _exchange_code_for_user(config, str(code))
        if data.get("open_id"):
            return {
                "open_id": data.get("open_id"),
                "name": data.get("name", "FeishuUser"),
                "email": data.get("email", ""),
                "source": "feishu_oauth_code",
            }

    user_access_token = qp.get("user_access_token")
    if user_access_token and feishu_cfg.get("base_url"):
        data = _fetch_user_by_access_token(feishu_cfg["base_url"], str(user_access_token))
        if data.get("open_id"):
            return {
                "open_id": data.get("open_id"),
                "name": data.get("name", "FeishuUser"),
                "email": data.get("email", ""),
                "source": "feishu_api",
            }

    return {
        "open_id": "ou_guest_demo",
        "name": "访客用户",
        "email": "",
        "source": "demo",
    }
