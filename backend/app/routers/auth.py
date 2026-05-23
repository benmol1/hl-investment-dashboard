from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
import duckdb

from app.auth import create_access_token, verify_password
from app.db import get_db

router = APIRouter()


@router.post("/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    con: duckdb.DuckDBPyConnection = Depends(get_db),
):
    """
    Authenticate with username + password (form-urlencoded).
    Returns a Bearer JWT valid for 24 hours.
    """
    row = con.execute(
        "SELECT id, hashed_password, role FROM users WHERE username = ?",
        (form.username,),
    ).fetchone()

    # Guard against missing user, unset password (NULL), or wrong password
    if not row or row[1] is None or not verify_password(form.password, row[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(user_id=row[0], role=row[2])
    return {"access_token": token, "token_type": "bearer"}
