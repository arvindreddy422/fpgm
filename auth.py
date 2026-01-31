import base64
import hashlib
import hmac
from functools import wraps

import bcrypt
from flask import request, make_response, redirect

from config import SESSION_COOKIE, SESSION_SECRET, SESSION_MAX_AGE


def _sign(value: str) -> str:
    return hmac.new(
        SESSION_SECRET.encode(), value.encode(), hashlib.sha256
    ).hexdigest()


def create_session_token(user_id: str) -> str:
    payload = base64.urlsafe_b64encode(user_id.encode()).decode().rstrip("=")
    signature = _sign(payload)
    return f"{payload}.{signature}"


def verify_session_token(token: str) -> str | None:
    if not token or "." not in token:
        return None
    payload, _, signature = token.partition(".")
    if not payload or not signature or _sign(payload) != signature:
        return None
    try:
        pad = 4 - len(payload) % 4
        if pad != 4:
            payload += "=" * pad
        return base64.urlsafe_b64decode(payload).decode()
    except Exception:
        return None


def get_session_user_id() -> str | None:
    """Get user ID from session cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    return verify_session_token(token)


def set_session_cookie(response, user_id: str) -> None:
    """Set session cookie on response."""
    token = create_session_token(user_id)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response) -> None:
    """Clear session cookie."""
    response.delete_cookie(key=SESSION_COOKIE, path="/")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def require_user(f):
    """Decorator to require authentication for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_session_user_id()
        if not user_id:
            from_path = request.path
            return redirect(f"/login?from={from_path}")
        return f(user_id=user_id, *args, **kwargs)
    return decorated_function
