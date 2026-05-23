"""
Authentication helpers: password hashing, JWT creation/verification,
and FastAPI dependencies for protecting routes and scoping data to users.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import duckdb
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app.db import get_db

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_HOURS = 24

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login")


def _jwt_secret() -> str:
    """Return JWT_SECRET, raising clearly if it is not configured."""
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET environment variable is not set.\n"
            "Generate one with:\n"
            '  python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return secret


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[_JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


class CurrentUser:
    """Lightweight value object injected into protected route handlers."""

    __slots__ = ("user_id", "role")

    def __init__(self, user_id: str, role: str) -> None:
        self.user_id = user_id
        self.role = role


def get_current_user(token: str = Depends(_oauth2)) -> CurrentUser:
    """Validate the Bearer token and return the authenticated user."""
    payload = _decode_token(token)
    user_id: Optional[str] = payload.get("sub")
    role: Optional[str] = payload.get("role")
    if not user_id or not role:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return CurrentUser(user_id=user_id, role=role)


def get_user_accounts(
    user: CurrentUser = Depends(get_current_user),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
) -> frozenset[str]:
    """
    Return the set of account_names (e.g. {'ISA', 'SIPP'}) that the
    authenticated user is permitted to see. All mart queries are scoped
    to this set at the API layer.
    """
    rows = con.execute(
        "SELECT id FROM accounts WHERE user_id = ?", (user.user_id,)
    ).fetchall()
    return frozenset(r[0] for r in rows)


# ---------------------------------------------------------------------------
# SQL query helper
# ---------------------------------------------------------------------------


def build_account_filter(
    user_accounts: frozenset[str],
    account: Optional[str] = None,
    *,
    column: str = "account_name",
) -> tuple[str, list]:
    """
    Build the SQL condition (without AND/WHERE prefix) that restricts a mart
    query to the accounts visible to the current user, optionally narrowed by
    an explicit account filter from the request query string.

    Returns:
        (condition, params)  — e.g. ("account_name IN (?, ?)", ["ISA", "SIPP"])

    If the intersection is empty (user has no access to the requested account),
    returns ("1=0", []) which produces zero rows from any query.
    """
    visible: frozenset[str] = (
        frozenset([account]) & user_accounts if account else user_accounts
    )
    if not visible:
        return "1=0", []
    placeholders = ", ".join("?" * len(visible))
    return f"{column} IN ({placeholders})", list(visible)
