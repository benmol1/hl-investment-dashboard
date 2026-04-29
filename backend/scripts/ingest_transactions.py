"""
Parse an HL transaction history CSV and upsert rows into DuckDB.

HL CSV columns (confirmed from sample export):
    Trade_date, Settle_date, Reference, Description, Unit_cost_pence, Quantity, Value_GBP

Usage:
    python backend/scripts/ingest_transactions.py \
        --file data/imports/HL_stock_share_ISA_tx_raw.csv \
        --account ISA

    python backend/scripts/ingest_transactions.py \
        --file data/imports/HL_SIPP_tx_raw.csv \
        --account SIPP
"""

import argparse
import csv
import hashlib
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "hl_dashboard.duckdb"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_date(s: str) -> Optional[date]:
    s = s.strip()
    if not s:
        return None
    from datetime import datetime
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
      - B[digits]   → BUY
      - BX[digits]  → SWITCH_IN  (buy leg of a fund class switch)
      - X[digits]   → SWITCH_OUT (sell leg of a fund class switch)
      - URIB...     → REBATE     (unit rebate reinvestment cash credit)
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

    if ref == "Transfer":
        return "TRANSFER", None

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
    """
    Returns {normalised_fund_name: fund_id} from the funds table.
    Normalisation: lowercase + collapse whitespace.
    """
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
    # Verify account exists
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
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for line_num, row in enumerate(reader, start=2):  # line 1 = header
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

            # Resolve fund for buy/sell transactions
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

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest HL transaction CSV into DuckDB")
    parser.add_argument("--file", required=True, help="Path to HL transaction CSV")
    parser.add_argument(
        "--account",
        required=True,
        choices=["ISA", "SIPP"],
        help="Account type the CSV belongs to",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}")
        sys.exit(1)

    print(f"Ingesting {file_path.name} -> account={args.account}")
    con = duckdb.connect(str(DB_PATH))
    ingest(file_path, args.account, con)
    con.close()
    print("Done.")


if __name__ == "__main__":
    main()
