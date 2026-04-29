import duckdb
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "hl_dashboard.duckdb"


def get_db():
    """
    FastAPI dependency: opens a read-only DuckDB connection per request.
    Read-only keeps the API safe to run alongside the ingestion/price scripts,
    which open their own short-lived read-write connections.
    """
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        yield con
    finally:
        con.close()
