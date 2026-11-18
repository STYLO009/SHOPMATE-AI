"""Authentication service: register, login, Google OAuth, sessions.

Security notes:
- Passwords are bcrypt-hashed (utils/security.py); plain text never stored.
- Google sign-in uses the real OAuth 2.0 authorization-code flow; id_tokens are
  verified against Google's JWKS (googleapis.com) before a session is issued.
- Sessions are JWTs validated on every protected request by the API layer
  (independent of any frontend route protection).
"""

import logging
import time
from typing import Optional

import httpx
import jwt as pyjwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.schemas.auth_schema import AuthResponse, UserOut
from app.utils.security import create_access_token, hash_password, verify_password

logger = logging.getLogger("shopmate.auth")

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class AuthError(Exception):
    """Domain error carrying an HTTP-friendly code."""

    def __init__(self, message: str, status_code: int = 400, code: str = "auth_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _issue(user: User) -> AuthResponse:
    token = create_access_token(subject=user.id, extra={"email": user.email})
    return AuthResponse(access_token=token, user=UserOut.model_validate(user))


def register_user(
    db: Session, full_name: str, email: str, password: str, accept_terms: bool
) -> AuthResponse:
    if not accept_terms:
        raise AuthError("You must accept the Terms and Privacy Policy.", code="terms_required")
    email = email.strip().lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise AuthError("An account with this email already exists.", status_code=409,
                        code="email_taken")
    user = User(
        full_name=full_name.strip(),
        email=email,
        hashed_password=hash_password(password),
        auth_provider="email_password",
        # Development convenience: SMTP not configured => verified on signup.
        email_verified=bool(settings.smtp_host) is False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user_registered user_id=%s provider=email_password", user.id)
    return _issue(user)


def login_user(db: Session, email: str, password: str) -> AuthResponse:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    # Deliberately generic message: do not leak which emails exist.
    if not user or not user.hashed_password:
        raise AuthError("Invalid email or password.", status_code=401, code="invalid_credentials")
    if not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password.", status_code=401, code="invalid_credentials")
    if not user.is_active:
        raise AuthError("This account has been deactivated.", status_code=403, code="inactive")
    logger.info("user_login user_id=%s provider=%s", user.id, user.auth_provider)
    return _issue(user)


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.scalar(select(User).where(User.id == user_id))


# --------------------------------------------------------------------------
# Google OAuth 2.0 (authorization code flow)
# --------------------------------------------------------------------------

def google_authorization_url() -> str:
    """Build the Google consent URL. Raises AuthError when not configured."""
    if not settings.google_oauth_configured:
        raise AuthError(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in the backend environment.",
            status_code=503,
            code="google_oauth_not_configured",
        )
    from urllib.parse import urlencode

    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account",
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


async def _verify_google_id_token(id_token: str) -> dict:
    """Verify a Google id_token signature against Google's JWKS."""
    unverified = pyjwt.decode(id_token, options={"verify_signature": False})
    issuer = unverified.get("iss", "")
    if issuer not in ("https://accounts.google.com", "accounts.google.com"):
        raise AuthError("Invalid Google token issuer.", status_code=401,
                        code="google_invalid_token")

    async with httpx.AsyncClient(timeout=15.0) as client:
        jwks_resp = await client.get(GOOGLE_JWKS_URL)
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json()

    keys = {k.get("kid"): k for k in jwks.get("keys", [])}
    header = pyjwt.get_unverified_header(id_token)
    key = keys.get(header.get("kid")) or next(iter(keys.values()), None)
    if not key:
        raise AuthError("Unable to validate Google token.", status_code=401,
                        code="google_invalid_token")

    from jwt.algorithms import RSAAlgorithm

    public_key = RSAAlgorithm.from_jwk(key)
    claims = pyjwt.decode(
        id_token,
        public_key,
        algorithms=["RS256"],
        audience=settings.google_client_id,
        issuer=issuer,
    )
    return claims


async def google_oauth_callback(db: Session, code: str) -> AuthResponse:
    """Exchange an authorization code for a Google profile, then a session."""
    if not settings.google_oauth_configured:
        raise AuthError("Google OAuth is not configured.", status_code=503,
                        code="google_oauth_not_configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            logger.warning("google_token_exchange_failed status=%s", token_resp.status_code)
            raise AuthError("Google sign-in failed (token exchange).", status_code=401,
                            code="google_token_exchange_failed")
        token_data = token_resp.json()

    id_token = token_data.get("id_token")
    if not id_token:
        raise AuthError("Google did not return an id_token.", status_code=401,
                        code="google_no_id_token")

    claims = await _verify_google_id_token(id_token)
    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise AuthError("Google account has no email.", status_code=401,
                        code="google_no_email")

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            full_name=claims.get("name") or email.split("@")[0],
            email=email,
            hashed_password=None,
            profile_image_url=claims.get("picture"),
            auth_provider="google",
            email_verified=bool(claims.get("email_verified")),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("user_registered user_id=%s provider=google", user.id)
    else:
        # Link existing password account to Google on first OAuth login.
        if user.auth_provider == "email_password":
            user.auth_provider = "google"
            if claims.get("picture"):
                user.profile_image_url = claims["picture"]
            db.commit()
            db.refresh(user)
        if not user.is_active:
            raise AuthError("This account has been deactivated.", status_code=403,
                            code="inactive")

    logger.info("google_login user_id=%s", user.id)
    return _issue(user)
