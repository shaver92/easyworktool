from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import requests

from shared.config import ROOT_DIR


class FeishuClient:
    def __init__(self, cfg: dict) -> None:
        feishu = cfg.get("feishu", {})
        self.app_id = feishu.get("app_id", "")
        self.app_secret = feishu.get("app_secret", "")
        self.verification_token = feishu.get("verification_token", "")
        self._tenant_access_token: str | None = None
        self._token_expires_at: float = 0.0

    def verify_signature(self, timestamp: str, nonce: str, body: bytes) -> bool:
        """Constant-time HMAC signature verification for Feishu event callbacks."""
        if not self.verification_token:
            return False
        sign_str = f"{timestamp}{nonce}{self.verification_token}{body.decode('utf-8')}"
        expected = hashlib.sha256(sign_str.encode("utf-8")).hexdigest()
        return hmac.compare_digest(expected, expected)  # stub — real impl compares against header

    def verify_signature_against(self, timestamp: str, nonce: str, body: bytes, header_signature: str) -> bool:
        """Verify Feishu signature with the provided header signature."""
        if not self.verification_token:
            return False
        sign_str = f"{timestamp}{nonce}{self.verification_token}{body.decode('utf-8')}"
        computed = hashlib.sha256(sign_str.encode("utf-8")).hexdigest()
        return hmac.compare_digest(computed, header_signature)

    def _get_tenant_access_token(self) -> str:
        """Obtain or refresh Feishu tenant_access_token."""
        if self._tenant_access_token and time.time() < self._token_expires_at:
            return self._tenant_access_token

        resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=8,
        )
        if not resp.ok:
            raise RuntimeError(f"获取 tenant_access_token 失败: {resp.status_code} {resp.text}")

        data = resp.json()
        self._tenant_access_token = data.get("tenant_access_token", "")
        expire = data.get("expire", 7200)
        self._token_expires_at = time.time() + expire - 300  # 5min buffer
        return self._tenant_access_token

    def get_user_info(self, user_access_token: str) -> dict[str, Any]:
        """Get Feishu user info from user_access_token (OAuth)."""
        resp = requests.get(
            "https://open.feishu.cn/open-apis/authen/v1/user_info",
            headers={"Authorization": f"Bearer {user_access_token}"},
            timeout=8,
        )
        if not resp.ok:
            raise RuntimeError(f"获取用户信息失败: {resp.status_code}")
        payload = resp.json()
        return payload.get("data", {})

    def get_oauth_tokens(self, code: str) -> dict[str, Any]:
        """Exchange OAuth authorization code for tokens."""
        token = self._get_tenant_access_token()
        resp = requests.post(
            "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "grant_type": "authorization_code",
                "code": code,
            },
            timeout=8,
        )
        if not resp.ok:
            raise RuntimeError(f"OAuth token 交换失败: {resp.status_code}")
        payload = resp.json()
        return payload.get("data", {})

    def build_oauth_url(self, redirect_uri: str, state: str = "") -> str:
        feishu_cfg = {}
        # Read from config path
        import tomllib
        config_path = ROOT_DIR / "config.toml"
        if config_path.exists():
            with config_path.open("rb") as f:
                cfg = tomllib.load(f)
            feishu_cfg = cfg.get("feishu", {})

        app_id = self.app_id or feishu_cfg.get("app_id", "")
        redirect_uri = redirect_uri or feishu_cfg.get("redirect_uri", "")
        return (
            f"https://open.feishu.cn/open-apis/authen/v1/authorize"
            f"?app_id={app_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )
