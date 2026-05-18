from __future__ import annotations

import json
import hashlib
import hmac as hmac_mod

import pytest
from fastapi.testclient import TestClient

from bot.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestURLChallenge:
    def test_url_challenge_returns_challenge(self, client):
        resp = client.get("/webhook?challenge=test_challenge_token")
        assert resp.status_code == 200
        assert resp.text == "test_challenge_token"

    def test_url_challenge_missing_param(self, client):
        resp = client.get("/webhook")
        assert resp.status_code == 400


class TestSignatureVerification:
    def test_valid_signature(self, client):
        from bot.main import feishu
        if not feishu or not feishu.verification_token:
            pytest.skip("No verification token configured")

        body = json.dumps({"type": "im.message.receive_v1", "event": {}, "header": {}})
        timestamp = "1234567890"
        nonce = "test_nonce"
        sign_str = f"{timestamp}{nonce}{feishu.verification_token}{body}"
        signature = hashlib.sha256(sign_str.encode("utf-8")).hexdigest()

        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Lark-Request-Timestamp": timestamp,
                "X-Lark-Request-Nonce": nonce,
                "X-Lark-Signature": signature,
            },
        )
        # Should be 200 (ack), not 401
        assert resp.status_code == 200


class TestMessageHandling:
    def test_empty_message_acks(self, client):
        payload = {
            "type": "im.message.receive_v1",
            "header": {"event_id": "evt_001"},
            "event": {
                "message": {"content": json.dumps({"text": ""})},
                "sender": {"sender_id": {"open_id": "ou_test"}},
            },
        }
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_duplicate_event_skipped(self, client):
        payload = {
            "type": "im.message.receive_v1",
            "header": {"event_id": "evt_dup_001"},
            "event": {
                "message": {"content": json.dumps({"text": "128 餐饮 午餐"})},
                "sender": {"sender_id": {"open_id": "ou_test"}},
            },
        }
        # First request
        resp1 = client.post("/webhook", json=payload)
        assert resp1.status_code == 200

        # Duplicate
        resp2 = client.post("/webhook", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["code"] == 0

    def test_invalid_json(self, client):
        resp = client.post("/webhook", content="not json")
        assert resp.status_code == 400
