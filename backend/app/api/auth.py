"""Auth endpoints: register, login, logout, me, Google OAuth, forgot-password."""

import logging
import hashlib
import smtplib
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import COOKIE_NAME, get_current_user
from app.core.config import settings
from app.database.connection import get_db
from app.models.user import User
from app.models.user import PasswordResetToken
from app.schemas.auth_schema import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    UserOut,
)
from app.services import auth_service
from app.services.auth_service import AuthError
from app.utils.security import hash_password

logger = logging.getLogger("shopmate.api.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    """Store the JWT in an httpOnly cookie (readable only by the backend)."""
    max_age = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/",
    )


def _auth_response_with_cookie(response: Response, result: AuthResponse) -> AuthResponse:
    _set_session_cookie(response, result.access_token)
    return result


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    try:
        result = auth_service.register_user(
            db,
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
            accept_terms=payload.accept_terms,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code,
                                                                "message": exc.message})
    return _auth_response_with_cookie(response, result)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        result = auth_service.login_user(db, email=payload.email, password=payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code,
                                                                "message": exc.message})
    return _auth_response_with_cookie(response, result)


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return MessageResponse(message="Signed out successfully.")


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Issue a short-lived, single-use reset token and email it when configured."""
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user and user.hashed_password:
        token = secrets.token_urlsafe(32)
        db.execute(update(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        ).values(used_at=datetime.now(timezone.utc)))
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        ))
        db.commit()
        if settings.smtp_host:
            reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"
            message = EmailMessage()
            message["Subject"] = "Reset your ShopMate AI password"
            message["From"] = settings.email_from
            message["To"] = user.email
            message.set_content(
                f"Use this link within 30 minutes to reset your password:\n\n{reset_url}\n\n"
                "If you did not request this, you can ignore this email."
            )
            try:
                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                    if settings.smtp_use_tls:
                        smtp.starttls()
                    if settings.smtp_user:
                        smtp.login(settings.smtp_user, settings.smtp_password)
                    smtp.send_message(message)
            except (OSError, smtplib.SMTPException):
                logger.exception("password_reset_email_failed user_id=%s", user.id)
    return MessageResponse(
        message="If an account exists for that email, a password reset link has been sent."
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = db.scalar(select(PasswordResetToken).where(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used_at.is_(None),
    ))
    now = datetime.now(timezone.utc)
    expiry = reset.expires_at if reset else None
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if reset is None or expiry is None or expiry <= now:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_reset_token",
            "message": "This password reset link is invalid or expired.",
        })
    user = db.get(User, reset.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_reset_token",
            "message": "This password reset link is invalid or expired.",
        })
    user.hashed_password = hash_password(payload.password)
    reset.used_at = now
    db.execute(update(PasswordResetToken).where(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != reset.id,
        PasswordResetToken.used_at.is_(None),
    ).values(used_at=now))
    db.commit()
    return MessageResponse(message="Your password has been reset. You can now sign in.")


# --------------------------------------------------------------------------
# Google OAuth 2.0
# --------------------------------------------------------------------------

@router.get("/google/login")
async def google_login(request: Request):
    """Redirect the browser to Google's consent screen."""
    try:
        url = auth_service.google_authorization_url()
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": exc.message})
    # Keep the user's intended destination across the OAuth round-trip.
    state = secrets.token_urlsafe(16)
    dest = str(request.query_params.get("next") or "/dashboard")
    response = Response(status_code=status.HTTP_302_FOUND)
    response.headers["Location"] = url + f"&state={state}"
    cookie_options = {
        "max_age": 600,
        "httponly": True,
        "secure": settings.environment == "production",
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie("oauth_state", state, **cookie_options)
    response.set_cookie("oauth_next", dest, **cookie_options)
    return response


@router.get("/google/callback", response_model=AuthResponse)
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Google redirects here; we validate the code server-side and issue a session."""
    if error:
        raise HTTPException(status_code=401,
                            detail={"code": "google_denied",
                                    "message": f"Google sign-in was cancelled ({error})."})
    if not code:
        raise HTTPException(status_code=400,
                            detail={"code": "missing_code", "message": "Missing authorization code."})

    expected_state = request.cookies.get("oauth_state")
    if not expected_state or not secrets.compare_digest(expected_state, state or ""):
        raise HTTPException(status_code=400,
                            detail={"code": "state_mismatch", "message": "Invalid OAuth state."})

    try:
        result = await auth_service.google_oauth_callback(db, code)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": exc.message})
    except Exception:  # network/JWKS failures
        logger.exception("google_callback_failed")
        raise HTTPException(status_code=502,
                            detail={"code": "google_unavailable",
                                    "message": "Could not reach Google to verify the sign-in."})

    dest = request.cookies.get("oauth_next", "/dashboard")
    if not dest.startswith("/") or dest.startswith("//") or "\\" in dest:
        dest = "/dashboard"
    redirect = RedirectResponse(
        url=f"{settings.frontend_url.rstrip('/')}{dest}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    _set_session_cookie(redirect, result.access_token)
    redirect.delete_cookie("oauth_state", path="/")
    redirect.delete_cookie("oauth_next", path="/")
    return redirect
