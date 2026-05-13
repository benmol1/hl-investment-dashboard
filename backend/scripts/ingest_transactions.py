"""
Ingest HL transaction CSVs from data/imports/raw_transactions/{ISA,SIPP}/ into DuckDB.

On each run:
  1. Any file in a raw_transactions subfolder that does not already follow the
     {ACCOUNT}_{YYYY-MM-DD}.csv naming convention is renamed using the file's
     creation date before processing.
  2. All CSV files in each subfolder are processed and upserted into the
     transactions table (already-present rows are silently skipped).

Raw HL CSV format:
  - Lines 1-5: metadata (portfolio summary, client name/number, valuation date, blank)
  - Line 6:    column headers
  - Line 7+:   data rows

Raw column headers -> internal names:
    Trade date      -> Trade_date
    Settle date     -> Settle_date
    Reference       -> Reference
    Description     -> Description
    Unit cost (p)   -> Unit_cost_pence
    Quantity        -> Quantity
    Value (£)       -> Value_GBP
"""

import csv
import hashlib
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "hl_dashboard.duckdb"
RAW_TX_DIR = ROOT / "data" / "imports" / "raw_transactions"
ACCOUNTS = ["ISA", "SIPP"]
SKIP_ROWS = 5

_RENAMED_PATTERN = re.compile(r"^(ISA|SIPP)_\d{4}-\d{2}-\d{2}(?:_\d+)?\.csv$")

# Substring-based mapping so column matching survives minor HL formatting changes
# (e.g. £ encoding differences). Checked in order; first match wins.
_COLUMN_REMAP: list[tuple[str, str]] = [
    ("Trade date", "Trade_date"),
    ("Settle date", "Settle_date"),
    ("Unit cost", "Unit_cost_pence"),
    ("Value", "Value_GBP"),
    ("Reference", "Reference"),
    ("Description", "Description"),
    ("Quantity", "Quantity"),
]


# ---------------------------------------------------------------------------
# File renaming
# ---------------------------------------------------------------------------

def _rename_raw_files() -> list[tuple[Path, str]]:
    """
    Scan each account subfolder. Rename any file not already following the
    {ACCOUNT}_{YYYY-MM-DD}.csv convention to that convention using the file's
    creation date. Returns a sorted list of (file_path, account_id) for every
    CSV found (renamed or not).
    """
    results: list[tuple[Path, str]] = []

    for account in ACCOUNTS:
        folder = RAW_TX_DIR / account
        if not folder.exists():
            continue

        for f in sorted(folder.glob("*.csv")):
            if _RENAMED_PATTERN.match(f.name) or f.stem.endswith("_manual"):
                results.append((f, account))
                continue

            created = datetime.fromtimestamp(f.stat().st_ctime).date()
            base_name = f"{account}_{created}.csv"
            new_path = folder / base_name

            # Avoid collisions if two files share the same creation date
            counter = 1
            while new_path.exists():
                new_path = folder / f"{account}_{created}_{counter}.csv"
                counter += 1

            f.rename(new_path)
            print(f"  Renamed: {f.name} -> {new_path.name}")
            results.append((new_path, account))

    return results


# ---------------------------------------------------------------------------
# Column header normalisation
# ---------------------------------------------------------------------------

def _remap_headers(raw_headers: list[str]) -> list[str]:
    """Map raw HL column names to internal names using substring matching."""
    remapped = []
    for h in raw_headers:
        internal = h  # default: keep original if no match
        for pattern, name in _COLUMN_REMAP:
            if pattern.lower() in h.lower():
                internal = name
                break
        remapped.append(internal)
    return remapped


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_date(s: str) -> Optional[date]:
    s = s.strip()
    if not s:
        return None
    return datetime.strptime(s, "%d/%m/%Y").date()


def parse_float(s: str) -> Optional[float]:
    """Handle 'n/a', empty strings, and quoted numbers containing commas."""
    s = s.strip().strip('"').replace(",", "")
    if not s or s.lower() == "n/a":
        return None
    return float(s)


def make_tx_id(account_id: str, trade_date: date, reference: str, value_gbp: float) -> str:
    key = f"{account_id}|{trade_date}|{reference}|{value_gbp}"
    return hashlib.md5(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Transaction type classification
# ---------------------------------------------------------------------------

def classify_transaction(reference: str, value_gbp: float) -> tuple[str, Optional[str]]:
    """
    Classify a transaction based on its HL reference string.

    Returns (transaction_type, transaction_subtype).

    Named references (REG. SAVER etc.) are handled explicitly.
    Patterned references follow HL's trade reference conventions:
      - B[digits]   -> BUY
      - BX[digits]  -> SWITCH_IN  (buy leg of a fund class switch)
      - X[digits]   -> SWITCH_OUT (sell leg of a fund class switch)
      - URIB...     -> REBATE     (unit rebate reinvestment cash credit)
    """
    ref = reference.strip()

    if ref.startswith("BX") and re.match(r"^BX\d", ref):
        return "SWITCH_IN", "Fund class switch"

    if ref.startswith("X") and re.match(r"^X\d", ref):
        return "SWITCH_OUT", "Fund class switch"

    if re.match(r"^B\d", ref):
        return "BUY", None

    if re.match(r"^S\d", ref):
        return "SELL", None

    if ref == "REG. SAVER":
        if value_gbp >= 0:
            return "CONTRIBUTION", "Regular"
        return "REJECTED", "Regular saver rejected"

    if ref in ("Card Web", "FPC"):
        return "CONTRIBUTION", "One-off"

    if ref == "MANAGE FEE":
        return "FEE", "Management fee"

    if ref == "INTEREST":
        return "INTEREST", None

    if ref in ("Transfer", "BACS"):
        return "TRANSFER", "Transfer in"

    if ref.upper().startswith("URIB"):
        return "REBATE", "Unit rebate"

    return "OTHER", None


# ---------------------------------------------------------------------------
# Fund name extraction and matching
# ---------------------------------------------------------------------------

def extract_fund_name(description: str) -> Optional[str]:
    """
    HL description format for fund purchases:
        'Fund Name (GBP) 22.481 @  222.410000'
    Returns the fund name portion, stripped.
    """
    match = re.match(r"^(.+?)\s*\(GBP\)", description)
    if match:
        return match.group(1).strip()
    return None


def build_fund_lookup(con: duckdb.DuckDBPyConnection) -> dict[str, str]:
    """Returns {normalised_fund_name: fund_id} from the funds table."""
    rows = con.execute("SELECT id, name FROM funds").fetchall()
    return {" ".join(name.lower().split()): fund_id for fund_id, name in rows}


def match_fund(description: str, lookup: dict[str, str]) -> Optional[str]:
    """Attempt to resolve fund_id from a transaction description."""
    fund_name = extract_fund_name(description)
    if not fund_name:
        return None
    key = " ".join(fund_name.lower().split())
    return lookup.get(key)


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest(file_path: Path, account_id: str, con: duckdb.DuckDBPyConnection) -> None:
    exists = con.execute(
        "SELECT 1 FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    if not exists:
        print(f"ERROR: account '{account_id}' not found in database. Run setup_db.py first.")
        sys.exit(1)

    fund_lookup = build_fund_lookup(con)
    warnings: list[str] = []
    rows_before = con.execute(
        "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    processed = 0
    with open(file_path, newline="", encoding="cp1252") as f:
        for _ in range(SKIP_ROWS):
            next(f)

        raw_reader = csv.reader(f)
        raw_headers = next(raw_reader)
        fieldnames = _remap_headers(raw_headers)

        # Data rows start at absolute line SKIP_ROWS + 2 (header is SKIP_ROWS + 1)
        reader = csv.DictReader(f, fieldnames=fieldnames)
        for line_num, row in enumerate(reader, start=SKIP_ROWS + 2):
            trade_date = parse_date(row["Trade_date"])
            settle_date = parse_date(row["Settle_date"])
            reference = row["Reference"].strip()
            description = row["Description"].strip()
            unit_cost_pence = parse_float(row["Unit_cost_pence"])
            quantity = parse_float(row["Quantity"])
            value_gbp = parse_float(row["Value_GBP"])

            if value_gbp is None:
                warnings.append(f"Line {line_num}: could not parse Value_GBP — skipping")
                continue

            tx_type, tx_subtype = classify_transaction(reference, value_gbp)

            fund_id: Optional[str] = None
            if tx_type in ("BUY", "SELL", "SWITCH_IN", "SWITCH_OUT") and description:
                fund_id = match_fund(description, fund_lookup)
                if fund_id is None:
                    warnings.append(
                        f"Line {line_num}: could not match fund from description: '{description}'"
                    )

            tx_id = make_tx_id(account_id, trade_date, reference, value_gbp)

            con.execute(
                """
                INSERT OR IGNORE INTO transactions (
                    id, account_id, fund_id,
                    trade_date, settle_date,
                    reference, raw_description,
                    transaction_type, transaction_subtype,
                    unit_cost_pence, quantity, value_gbp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tx_id, account_id, fund_id,
                    trade_date, settle_date,
                    reference, description,
                    tx_type, tx_subtype,
                    unit_cost_pence, quantity, value_gbp,
                ),
            )
            processed += 1

    rows_after = con.execute(
        "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
    ).fetchone()[0]

    inserted = rows_after - rows_before
    skipped = processed - inserted
    print(f"  Processed: {processed}  Inserted: {inserted}  Already present (skipped): {skipped}")

    if warnings:
        print(f"\n  {len(warnings)} warning(s):")
        for w in warnings:
            print(f"    {w}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _ensure_ingest_log(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS ingest_log (
            run_at        TIMESTAMPTZ NOT NULL,
            source        TEXT        NOT NULL,
            rows_inserted INTEGER     NOT NULL DEFAULT 0,
            status        TEXT        NOT NULL,
            detail        TEXT
        )
    """)


def _write_log(con: duckdb.DuckDBPyConnection, rows_inserted: int, status: str, detail: Optional[str] = None) -> None:
    con.execute(
        "INSERT INTO ingest_log (run_at, source, rows_inserted, status, detail) VALUES (?, 'transactions', ?, ?, ?)",
        (datetime.now(timezone.utc), rows_inserted, status, detail),
    )


def main() -> None:
    print("Scanning for raw transaction files...")
    files = _rename_raw_files()

    if not files:
        print("No transaction files found in raw_transactions subfolders.")
        return

    con = duckdb.connect(str(DB_PATH))
    _ensure_ingest_log(con)
    total_inserted = 0
    try:
        for file_path, account_id in files:
            print(f"\nIngesting {file_path.name} -> account={account_id}")
            rows_before = con.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
            ).fetchone()[0]
            ingest(file_path, account_id, con)
            rows_after = con.execute(
                "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
            ).fetchone()[0]
            total_inserted += rows_after - rows_before
        _write_log(con, total_inserted, "success")
    except Exception as e:
        _write_log(con, total_inserted, "failure", str(e))
        raise
    finally:
        con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
