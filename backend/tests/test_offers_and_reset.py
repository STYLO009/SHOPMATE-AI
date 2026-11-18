"""Tests for the public offers gateway and the password-reset flow."""

from __future__ import annotations

import re
from unittest.mock import patch


def test_offers_search_is_public_and_never_returns_sample_data(client):
    """Live-offer search must stay empty without affiliate credentials."""
    resp = client.get("/api/offers/search", params={"query": "headphones"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["offers"] == []
    # Sample listings are structurally excluded from this endpoint.
    assert all(o["is_sample_data"] is False for o in body["offers"])
    # The missing feed is reported honestly instead of silently empty.
    assert body["provider_errors"], "expected an explicit provider error"
    assert "not_configured" in " ".join(body["provider_errors"])


def test_offers_search_requires_a_query(client):
    assert client.get("/api/offers/search", params={"query": ""}).status_code == 422


def test_offers_featured_reports_missing_feed_without_faking(client):
    resp = client.get("/api/offers/featured")
    assert resp.status_code == 200
    body = resp.json()
    assert body["offers"] == []
    assert all(o["is_sample_data"] is False for o in body["offers"])
    assert any("not_configured" in e for e in body["provider_errors"])


# ------------------------------------------------------------ reset password


class _CapturingSMTP:
    """Fake SMTP that records the outbound message body."""

    last_body: str | None = None

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        _CapturingSMTP.last_body = message.get_content()


def _register(client, email: str, password: str) -> None:
    resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Reset User",
            "email": email,
            "password": password,
            "confirm_password": password,
            "accept_terms": True,
        },
    )
    assert resp.status_code == 201, resp.text


def test_reset_password_full_flow(client):
    """forgot → email token → reset → login with the new password."""
    from app.core.config import settings

    _register(client, "reset@example.com", "OldPassw0rd1")

    previous_host = settings.smtp_host
    settings.smtp_host = "smtp.test.local"
    _CapturingSMTP.last_body = None
    try:
        with patch("app.api.auth.smtplib.SMTP", _CapturingSMTP):
            forgot = client.post(
                "/api/auth/forgot-password", json={"email": "reset@example.com"}
            )
    finally:
        settings.smtp_host = previous_host

    assert forgot.status_code == 200
    assert _CapturingSMTP.last_body, "reset email was never composed"
    match = re.search(r"token=([A-Za-z0-9_\-]+)", _CapturingSMTP.last_body)
    assert match, "reset link missing from email"
    token = match.group(1)

    reset = client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "NewPassw0rd1"},
    )
    assert reset.status_code == 200

    # Old password no longer works; new one does.
    old = client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "OldPassw0rd1"},
    )
    assert old.status_code == 401
    new = client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "NewPassw0rd1"},
    )
    assert new.status_code == 200

    # Tokens are single-use: replaying it must fail.
    replay = client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "AnotherPass1"},
    )
    assert replay.status_code == 400
    assert replay.json()["detail"]["code"] == "invalid_reset_token"


def test_reset_password_rejects_unknown_token(client):
    resp = client.post(
        "/api/auth/reset-password",
        json={"token": "t" * 43, "password": "NewPassw0rd1"},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_reset_token"


def test_reset_password_rejects_short_tokens(client):
    resp = client.post(
        "/api/auth/reset-password",
        json={"token": "short", "password": "NewPassw0rd1"},
    )
    assert resp.status_code == 422


def test_forgot_password_never_reveals_account_existence(client):
    """Same response for known and unknown emails (no enumeration)."""
    _register(client, "known@example.com", "Passw0rd123")
    known = client.post(
        "/api/auth/forgot-password", json={"email": "known@example.com"}
    )
    unknown = client.post(
        "/api/auth/forgot-password", json={"email": "ghost@example.com"}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
