"""FastAPI authentication dependencies (JWT validation)."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.services.auth_service import get_user_by_id
from app.utils.security import decode_access_token

COOKIE_NAME = "shopmate_token"
HEADER_PREFIX = "Bearer "


def _extract_token(request: Request) -> str | None:
    """Read JWT from Authorization header first, then the httpOnly cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith(HEADER_PREFIX):
        token = auth_header[len(HEADER_PREFIX):].strip()
        if token:
            return token
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Protected-route dependency — validates the session server-side."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required."},
        )
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Session is invalid or expired."},
        )
    user = get_user_by_id(db, payload.get("sub", ""))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Session is invalid or expired."},
        )
    return user


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Same as get_current_user but returns None instead of raising."""
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None
