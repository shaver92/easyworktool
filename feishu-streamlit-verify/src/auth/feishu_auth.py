from __future__ import annotations

from urllib.parse import quote
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


def _safe_post_json_with_meta(url: str, payload: dict, headers: dict | None = None) -> tuple[dict, dict]:
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=8)
        body = resp.json() if resp.content else {}
        return body if isinstance(body, dict) else {}, {
            "http_status": resp.status_code,
            "ok": resp.ok,
            "url": url,
        }
    except requests.RequestException as ex:
        return {}, {"http_status": None, "ok": False, "url": url, "exception": str(ex)}
    except ValueError:
        return {}, {"http_status": None, "ok": False, "url": url, "exception": "invalid_json_response"}


def _safe_get_json_with_meta(url: str, headers: dict | None = None, params: dict | None = None) -> tuple[dict, dict]:
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=8)
        body = resp.json() if resp.content else {}
        return body if isinstance(body, dict) else {}, {
            "http_status": resp.status_code,
            "ok": resp.ok,
            "url": url,
        }
    except requests.RequestException as ex:
        return {}, {"http_status": None, "ok": False, "url": url, "exception": str(ex)}
    except ValueError:
        return {}, {"http_status": None, "ok": False, "url": url, "exception": "invalid_json_response"}


def _fetch_user_by_access_token(base_url: str, user_access_token: str) -> dict:
    url = f"{base_url}/authen/v1/user_info"
    payload = _safe_get_json(url, headers={"Authorization": f"Bearer {user_access_token}"})
    return payload.get("data", {})


def _exchange_code_for_user(config: dict, code: str) -> tuple[dict, dict]:
    feishu_cfg = config.get("feishu", {})
    base_url = feishu_cfg.get("base_url", "")
    app_id = feishu_cfg.get("app_id", "")
    app_secret = feishu_cfg.get("app_secret", "")
    redirect_uri = feishu_cfg.get("redirect_uri", "")
    if not (base_url and app_id and app_secret):
        return {}, {"step": "precheck", "message": "missing_base_or_app_credentials"}

    oauth_payload, oauth_meta = _safe_post_json_with_meta(
        f"{base_url}/authen/v2/oauth/token",
        {
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": app_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    debug: dict = {
        "step": "oauth_token",
        "oauth_http_status": oauth_meta.get("http_status"),
        "oauth_ok": oauth_meta.get("ok"),
        "oauth_code": oauth_payload.get("code"),
        "oauth_msg": oauth_payload.get("msg"),
    }
    # Backward-compatible fallback for tenants/environments with old behavior.
    if not oauth_payload.get("data", {}).get("access_token"):
        app_token_payload, app_token_meta = _safe_post_json_with_meta(
            f"{base_url}/auth/v3/app_access_token/internal",
            {"app_id": app_id, "app_secret": app_secret},
        )
        app_access_token = app_token_payload.get("app_access_token", "")
        debug["fallback_app_token_http_status"] = app_token_meta.get("http_status")
        debug["fallback_app_token_ok"] = app_token_meta.get("ok")
        debug["fallback_app_token_code"] = app_token_payload.get("code")
        debug["fallback_app_token_msg"] = app_token_payload.get("msg")
        if app_access_token:
            oauth_payload, oauth_meta = _safe_post_json_with_meta(
                f"{base_url}/authen/v2/oauth/token",
                {"grant_type": "authorization_code", "code": code},
                headers={"Authorization": f"Bearer {app_access_token}"},
            )
            debug["fallback_oauth_http_status"] = oauth_meta.get("http_status")
            debug["fallback_oauth_ok"] = oauth_meta.get("ok")
            debug["fallback_oauth_code"] = oauth_payload.get("code")
            debug["fallback_oauth_msg"] = oauth_payload.get("msg")
    data = oauth_payload.get("data", {})
    user_access_token = data.get("access_token", "")
    if not user_access_token:
        debug["step"] = "oauth_token_missing_access_token"
        return {}, debug
    user_payload, user_meta = _safe_get_json_with_meta(
        f"{base_url}/authen/v1/user_info",
        headers={"Authorization": f"Bearer {user_access_token}"},
    )
    user_data = user_payload.get("data", {})
    debug["user_http_status"] = user_meta.get("http_status")
    debug["user_ok"] = user_meta.get("ok")
    debug["user_code"] = user_payload.get("code")
    debug["user_msg"] = user_payload.get("msg")
    if not user_data.get("open_id"):
        debug["step"] = "user_info_missing_open_id"
        return {}, debug
    debug["step"] = "ok"
    return user_data, debug


def resolve_user(config: dict) -> dict:
    st.session_state["auth_debug"] = {}
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
        data, debug = _exchange_code_for_user(config, str(code))
        st.session_state["auth_debug"] = debug
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


def build_oauth_login_url(config: dict, state: str = "mms_login") -> str:
    feishu_cfg = config.get("feishu", {})
    app_id = feishu_cfg.get("app_id", "")
    redirect_uri = feishu_cfg.get("redirect_uri", "")
    base_url = feishu_cfg.get("base_url", "")
    if not (app_id and redirect_uri and base_url):
        return ""
    encoded_redirect_uri = quote(redirect_uri, safe="")
    encoded_state = quote(state, safe="")
    return (
        f"{base_url}/authen/v1/index"
        f"?app_id={app_id}"
        f"&redirect_uri={encoded_redirect_uri}"
        f"&state={encoded_state}"
    )
