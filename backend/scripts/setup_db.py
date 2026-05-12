"""
One-time setup: create the DuckDB schema and seed all reference data.
Safe to re-run — schema uses CREATE IF NOT EXISTS and seed rows use INSERT OR IGNORE.

Usage:
    python backend/scripts/setup_db.py
"""

import csv
import re
import sys
from datetime import datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "hl_dashboard.duckdb"
MIGRATIONS_DIR = ROOT / "backend" / "migrations"
IMPORTS_DIR = ROOT / "data" / "imports"


def run_migrations(con: duckdb.DuckDBPyConnection) -> None:
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        print(f"  Running migration: {sql_file.name}")
        con.execute(sql_file.read_text(encoding="utf-8"))


def seed_accounts(con: duckdb.DuckDBPyConnection) -> None:
    rows = [
        ("ISA", "Stocks & Shares ISA"),
        ("SIPP", "Self-Invested Personal Pension"),
    ]
    for row in rows:
        con.execute(
            "INSERT OR IGNORE INTO accounts VALUES (?, ?)", row
        )
    print(f"  Seeded {len(rows)} accounts")


def seed_funds(con: duckdb.DuckDBPyConnection) -> None:
    funds_csv = IMPORTS_DIR / "funds.csv"
    if not funds_csv.exists():
        print("  WARNING: funds.csv not found — skipping fund seed")
        return

    inserted = 0
    with open(funds_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            isin = row["fund_ISIN"].strip()
            code = row["fund_code"].strip() or None
            name = row["fund_name"].strip()
            short_name = row["short_name"].strip() or None

            # Skip true placeholder rows only
            if not name or isin in ("??",) or name == "Not a fund":
                continue

            isin_value = isin if isin not in ("", "No_ISIN") else None

            # Use ISIN as primary key; generate a slug for funds without one
            if isin_value:
                fund_id = isin_value
            else:
                fund_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]

            con.execute(
                """
                INSERT OR REPLACE INTO funds (id, name, isin, morningstar_code, short_name)
                VALUES (?, ?, ?, ?, ?)
                """,
                (fund_id, name, isin_value, code, short_name),
            )
            inserted += 1

    print(f"  Seeded {inserted} funds")



def seed_dim_date(con: duckdb.DuckDBPyConnection) -> None:
    date_csv = IMPORTS_DIR / "dates.csv"
    if not date_csv.exists():
        print("  WARNING: dates.csv not found — skipping dim_date seed")
        return

    print("  Loading dim_date from CSV (this may take a moment for large files)...")
    # Use DuckDB's native CSV reader for speed — much faster than row-by-row Python
    con.execute(
        f"""
        INSERT OR IGNORE INTO dim_date
        SELECT
            strptime(CAST(Date AS VARCHAR), '%d/%m/%Y')::DATE AS date,
            CAST(Year AS INTEGER)                              AS year,
            CAST(Month AS INTEGER)                             AS month,
            CAST(Day AS INTEGER)                               AS day,
            "Year-month"                                       AS year_month,
            "Financial Year"                                   AS financial_year
        FROM read_csv_auto(
            '{date_csv.as_posix()}',
            header=true,
            columns={{'Date': 'VARCHAR', 'Year': 'INTEGER', 'Month': 'INTEGER', 'Day': 'INTEGER', 'Year-month': 'VARCHAR', 'Financial Year': 'VARCHAR'}}
        )
        """
    )
    count = con.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0]
    print(f"  dim_date loaded: {count:,} rows")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Opening database: {DB_PATH}")
    con = duckdb.connect(str(DB_PATH))

    print("Running migrations...")
    run_migrations(con)

    print("Seeding reference data...")
    seed_accounts(con)
    seed_funds(con)
    seed_dim_date(con)

    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
