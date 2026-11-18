"""Input validation helpers shared across services."""

import re
from typing import Optional
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

PASSWORD_MIN_LENGTH = 8


def is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email.strip()))


def validate_password(password: str) -> Optional[str]:
    """Return an error message if the password is too weak, else None."""
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
    if len(password.encode("utf-8")) > 72:
        return "Password must be no more than 72 UTF-8 bytes."
    if not re.search(r"[A-Za-z]", password):
        return "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one number."
    return None


def is_valid_url(url: Optional[str]) -> bool:
    """Validate http(s) URLs coming from providers or user input."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_text(text: str) -> str:
    """Lowercase + collapse whitespace for dedupe / comparison keys."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def product_dedupe_key(title: str, brand: Optional[str], merchant: str) -> str:
    return f"{normalize_text(brand or '')}|{normalize_text(title)}|{normalize_text(merchant)}"
