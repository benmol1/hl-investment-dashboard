"""
Identify and interactively drop orphaned tables from hl_dashboard.duckdb.

A table is considered orphaned if it is not:
  - a current dbt model (derived from `dbt ls`)
  - a raw source table managed by setup_db.py / ingest scripts

Usage (run from the repo root):
    python backend/scripts/cleanup_db.py
"""

import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "hl_dashboard.duckdb"
DBT_DIR = ROOT / "dbt"

# Raw source tables that are not dbt models and should never be dropped.
SOURCE_TABLES = {
    "accounts",
    "benchmarks",
    "funds",
    "ingest_log",
    "prices",
    "transaction_type_mapping",
    "transactions",
}


def get_dbt_models() -> set[str]:
    dbt = Path(sys.executable).parent / "dbt"
    result = subprocess.run(
        [str(dbt), "ls", "--profiles-dir", ".", "--output", "name"],
        cwd=DBT_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("ERROR: dbt ls failed:")
        print(result.stderr)
        sys.exit(1)
    return {line.strip().split(".")[-1] for line in result.stdout.splitlines() if line.strip()}


def get_db_tables(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    rows = con.execute("""
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'main'
    """).fetchall()
    return {r[0]: r[1] for r in rows}  # name -> 'BASE TABLE' or 'VIEW'


def main() -> None:
    print(f"Database: {DB_PATH}\n")

    print("Fetching current dbt models...")
    dbt_models = get_dbt_models()
    print(f"  {len(dbt_models)} models found.\n")

    con = duckdb.connect(str(DB_PATH))
    db_tables = get_db_tables(con)
    print(f"Objects in DuckDB: {len(db_tables)}\n")

    kept = SOURCE_TABLES | dbt_models
    orphans = {name: kind for name, kind in db_tables.items() if name not in kept}

    if not orphans:
        print("No orphaned objects found. Nothing to do.")
        con.close()
        return

    print(f"Orphaned objects ({len(orphans)}):")
    for name, kind in orphans.items():
        print(f"  - {name} ({kind.lower()})")

    print()
    dropped, skipped = [], []

    for name, kind in orphans.items():
        answer = input(f"Drop {kind.lower()} '{name}'? [y/N] ").strip().lower()
        if answer == "y":
            drop_cmd = "VIEW" if kind == "VIEW" else "TABLE"
            con.execute(f'DROP {drop_cmd} IF EXISTS "{name}"')
            print(f"  Dropped '{name}'.")
            dropped.append(name)
        else:
            print(f"  Skipped '{name}'.")
            skipped.append(name)

    con.close()

    print(f"\nDone. Dropped: {len(dropped)}, Skipped: {len(skipped)}.")
    if dropped:
        print("Dropped tables:", ", ".join(dropped))
    if skipped:
        print("Skipped tables:", ", ".join(skipped))


if __name__ == "__main__":
    main()
