"""Authentication tests: register, login, me, logout, OAuth, protection."""

import pytest


def test_register_success(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Alice Wonder",
            "email": "alice@example.com",
            "password": "Str0ngPass1",
            "confirm_password": "Str0ngPass1",
            "accept_terms": True,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["auth_provider"] == "email_password"
    # Password must never be echoed back (auth_provider string is fine).
    assert "Str0ngPass1" not in resp.text
    assert "password" not in body["user"]


def test_register_duplicate_email(client):
    payload = {
        "full_name": "Bob",
        "email": "bob@example.com",
        "password": "Str0ngPass1",
        "confirm_password": "Str0ngPass1",
        "accept_terms": True,
    }
    assert client.post("/api/auth/register", json=payload).status_code == 201
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "email_taken"


def test_register_rejects_weak_password(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Weak",
            "email": "weak@example.com",
            "password": "short",
            "confirm_password": "short",
            "accept_terms": True,
        },
    )
    assert resp.status_code == 422  # pydantic validation


def test_register_requires_terms(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "No Terms",
            "email": "terms@example.com",
            "password": "Str0ngPass1",
            "confirm_password": "Str0ngPass1",
            "accept_terms": False,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "terms_required"


def test_register_password_mismatch(client):
    resp = client.post(
        "/api/auth/register",
        json={
            "full_name": "Mismatch",
            "email": "mm@example.com",
            "password": "Str0ngPass1",
            "confirm_password": "Different1",
            "accept_terms": True,
        },
    )
    assert resp.status_code == 422


def test_login_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Carl",
            "email": "carl@example.com",
            "password": "Str0ngPass1",
            "confirm_password": "Str0ngPass1",
            "accept_terms": True,
        },
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "carl@example.com", "password": "WrongPass1"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


def test_login_unknown_email_same_error(client):
    """Must not reveal whether an email exists."""
    resp = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "Whatever123"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


def test_me_requires_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "not_authenticated"


def test_me_with_session(auth_client):
    resp = auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


def test_logout_clears_cookie(auth_client):
    resp = auth_client.post("/api/auth/logout")
    assert resp.status_code == 200
    # Cookie cleared → subsequent /me fails.
    assert auth_client.get("/api/auth/me").status_code == 401


def test_protected_endpoints_reject_anonymous(client):
    for method, path in [
        ("post", "/api/chat"),
        ("get", "/api/conversations"),
        ("get", "/api/watchlist"),
        ("post", "/api/recommendations"),
        ("post", "/api/reviews/analyze"),
    ]:
        resp = getattr(client, method)(
            path,
            **({} if method == "get" else
               {"json": {"message": "hi", "query": "hi", "product_id": "x"}}),
        )
        assert resp.status_code == 401, f"{method} {path} was unprotected"


def test_tampered_jwt_rejected(client):
    resp = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_token"


def test_google_login_not_configured_returns_503(client):
    """Without credentials the endpoint reports misconfiguration (never fakes)."""
    resp = client.get("/api/auth/google/login", follow_redirects=False)
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "google_oauth_not_configured"


def test_google_callback_without_code(client):
    resp = client.get("/api/auth/google/callback")
    assert resp.status_code in (400, 401, 503)


def test_forgot_password_never_enumerates(client):
    resp = client.post("/api/auth/forgot-password",
                       json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    assert "If an account exists" in resp.json()["message"]
