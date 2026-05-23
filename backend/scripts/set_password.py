"""
Set or reset the password for a dashboard user.

Usage:
    uv run python backend/scripts/set_password.py <username>

Example:
    uv run python backend/scripts/set_password.py owner
    uv run python backend/scripts/set_password.py demo

The script prompts for a new password (twice for confirmation), hashes it
with bcrypt, and stores the hash in the users table. The JWT_SECRET env var
is NOT required — this script only touches the DB, not JWT signing.
"""

import getpass
import os
import sys
from pathlib import Path

import duckdb
from passlib.context import CryptContext

ROOT = Path(__file__).resolve().parents[2]

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _db_path() -> Path:
    env = os.environ.get("HL_DB_PATH")
    return Path(env) if env else ROOT / "data" / "hl_dashboard.duckdb"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: set_password.py <username>", file=sys.stderr)
        sys.exit(1)

    username = sys.argv[1]

    password = getpass.getpass(f"New password for '{username}': ")
    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    hashed = _pwd_ctx.hash(password)
    db = _db_path()

    if not db.exists():
        print(f"Database not found: {db}", file=sys.stderr)
        print("Run setup_db.py first.", file=sys.stderr)
        sys.exit(1)

    con = duckdb.connect(str(db))
    row = con.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()

    if row is None:
        print(f"User '{username}' not found. Run setup_db.py first.", file=sys.stderr)
        con.close()
        sys.exit(1)

    con.execute(
        "UPDATE users SET hashed_password = ? WHERE username = ?",
        (hashed, username),
    )
    con.close()

    print(f"Password updated for '{username}'.")
    print("You can now log in via the dashboard.")


if __name__ == "__main__":
    main()
