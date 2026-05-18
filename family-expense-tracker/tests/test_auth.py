from __future__ import annotations

import time
import pytest
from web.auth import hash_pin, verify_pin, check_rate_limit, record_failed_attempt, reset_attempts

import streamlit as st


@pytest.fixture(autouse=True)
def reset_session_state():
    st.session_state.clear()


class TestPinHashing:
    def test_hash_produces_string(self):
        h = hash_pin("1234")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_same_pin_same_hash(self):
        assert hash_pin("5678") == hash_pin("5678")

    def test_different_pin_different_hash(self):
        assert hash_pin("1234") != hash_pin("5678")


class TestPinVerification:
    def test_correct_pin(self):
        h = hash_pin("1234")
        assert verify_pin(h, "1234") is True

    def test_wrong_pin(self):
        h = hash_pin("1234")
        assert verify_pin(h, "5678") is False

    def test_none_hash(self):
        assert verify_pin(None, "1234") is False

    def test_empty_pin(self):
        assert verify_pin(hash_pin("1234"), "") is False


class TestRateLimiting:
    def test_first_attempt_ok(self):
        blocked, wait = check_rate_limit(1)
        assert blocked is False
        assert wait == 0

    def test_after_max_attempts_blocked(self):
        uid = 99
        for _ in range(5):
            record_failed_attempt(uid)
        blocked, wait = check_rate_limit(uid)
        assert blocked is True
        assert wait > 0

    def test_reset_clears_attempts(self):
        uid = 98
        for _ in range(3):
            record_failed_attempt(uid)
        reset_attempts(uid)
        blocked, _ = check_rate_limit(uid)
        assert blocked is False
