"""
Fetch daily NAV prices for all funds in the database and store in the prices table.
Also fetches benchmark index levels (FTSE 100, S&P 500, Nasdaq) via yfinance.

Morningstar note:
    Fund prices are fetched from Morningstar's unofficial JSON API using the
    morningstar_code stored in the funds table (e.g. '0P0000SVHO').
    The API token in MORNINGSTAR_API_TOKEN is embedded in Morningstar's own
    web pages and has been stable for years, but may change. If fetches start
    returning 401/403, inspect the Network tab on morningstar.co.uk to find
    the current token.

Usage:
    # Fetch missing prices for currently held funds (normal daily run)
    python backend/scripts/fetch_prices.py

    # Fetch missing prices for all funds, including exited ones
    python backend/scripts/fetch_prices.py --all

    # Force full backfill from a given date for held funds only
    python backend/scripts/fetch_prices.py --backfill 2017-01-01

    # Force full backfill from a given date for all funds
    python backend/scripts/fetch_prices.py --all --backfill 2017-01-01
"""

import argparse
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import os

import duckdb
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "hl_dashboard.duckdb"

# Morningstar's unofficial history API — see module docstring if this stops working
MORNINGSTAR_API_TOKEN = os.getenv("MORNINGSTAR_API_TOKEN", "9vehuxllxs")
MORNINGSTAR_BASE = (
    f"https://tools.morningstar.co.uk/api/rest.svc/timeseries_price/{MORNINGSTAR_API_TOKEN}"
)

BENCHMARKS = [
    ("FTSE100", "^FTSE"),
    ("SP500", "^GSPC"),
    ("NASDAQ", "^IXIC"),
]

# Polite delay between Morningstar requests to avoid rate-limiting
REQUEST_DELAY_SECONDS = 1.5


# ---------------------------------------------------------------------------
# Morningstar
# ---------------------------------------------------------------------------

def fetch_morningstar_prices(
    morningstar_code: str, start: date, end: date
) -> list[tuple[date, float]]:
    """
    Returns list of (date, price_pence) for a fund.

    The Morningstar API returns a flat JSON array of [unix_timestamp_ms, price_gbp] pairs.
    We multiply by 100 to convert GBP -> pence for storage (consistent with HL transaction data).
    """
    params = {
        "id": f"{morningstar_code}]2]0]FOUK",
        "currencyId": "GBP",
        "idtype": "Morningstar",
        "frequency": "daily",
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "outputType": "COMPACTJSON",
    }
    resp = requests.get(MORNINGSTAR_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Response is [[timestamp_ms, price_gbp], ...]
    if not isinstance(data, list):
        return []

    results = []
    for entry in data:
        try:
            ts_ms, price_gbp = entry[0], entry[1]
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()
            price_pence = round(price_gbp * 100, 6)
            results.append((dt, price_pence))
        except (IndexError, TypeError, ValueError):
            continue

    return results


def insert_fund_prices(
    con: duckdb.DuckDBPyConnection,
    fund_id: str,
    prices: list[tuple[date, float]],
    source: str = "morningstar",
) -> int:
    inserted = 0
    for dt, price_pence in prices:
        con.execute(
            """
            INSERT OR IGNORE INTO prices (fund_id, date, price_pence, source)
            VALUES (?, ?, ?, ?)
            """,
            (fund_id, dt, price_pence, source),
        )
        inserted += 1
    return inserted


def get_fetch_start(
    con: duckdb.DuckDBPyConnection,
    fund_id: str,
    backfill_from: Optional[date],
) -> date:
    """
    If backfill_from is set, use that.
    Otherwise, start from the day after the latest price we already have.
    If no prices exist yet, start from the earliest transaction for this fund.
    """
    if backfill_from:
        return backfill_from

    latest = con.execute(
        "SELECT MAX(date) FROM prices WHERE fund_id = ?", (fund_id,)
    ).fetchone()[0]

    if latest:
        return latest + timedelta(days=1)

    earliest_tx = con.execute(
        "SELECT MIN(trade_date) FROM transactions WHERE fund_id = ?", (fund_id,)
    ).fetchone()[0]

    return earliest_tx or date(2017, 1, 1)


# ---------------------------------------------------------------------------
# Benchmarks via yfinance
# ---------------------------------------------------------------------------

def fetch_benchmarks(
    con: duckdb.DuckDBPyConnection, backfill_from: Optional[date]
) -> None:
    end = date.today()

    for index_id, ticker in BENCHMARKS:
        start = get_benchmark_start(con, index_id, backfill_from)
        if start >= end:
            print(f"  {index_id}: up to date")
            continue

        print(f"  {index_id} ({ticker}): fetching {start} to {end}")
        try:
            df = yf.download(ticker, start=start.isoformat(), end=end.isoformat(), progress=False)
        except Exception as e:
            print(f"    ERROR fetching {ticker}: {e}")
            continue

        if df.empty:
            print(f"    No data returned for {ticker}")
            continue

        inserted = 0
        for dt, row in df.iterrows():
            con.execute(
                """
                INSERT OR IGNORE INTO benchmarks (index_id, date, level, ticker)
                VALUES (?, ?, ?, ?)
                """,
                (index_id, dt.date(), float(row["Close"].iloc[0]), ticker),
            )
            inserted += 1

        print(f"    Inserted {inserted:,} rows")


def get_benchmark_start(
    con: duckdb.DuckDBPyConnection, index_id: str, backfill_from: Optional[date]
) -> date:
    if backfill_from:
        return backfill_from

    latest = con.execute(
        "SELECT MAX(date) FROM benchmarks WHERE index_id = ?", (index_id,)
    ).fetchone()[0]

    if latest:
        return latest + timedelta(days=1)

    return date(2017, 1, 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch fund prices and benchmark levels")
    parser.add_argument(
        "--backfill",
        metavar="YYYY-MM-DD",
        help="Force full fetch from this date (ignores existing data)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch prices for all funds in dim_fund, not just currently held ones",
    )
    args = parser.parse_args()

    backfill_from: Optional[date] = None
    if args.backfill:
        try:
            backfill_from = datetime.strptime(args.backfill, "%Y-%m-%d").date()
        except ValueError:
            print("ERROR: --backfill date must be in YYYY-MM-DD format")
            sys.exit(1)

    con = duckdb.connect(str(DB_PATH))
    today = date.today()

    # --- Fund prices via Morningstar ---
    status_filter = "" if args.all else "AND investment_status_indicator = 'Holding'"
    funds = con.execute(
        f"""
        SELECT fund_id, fund_name, morningstar_code
        FROM main.dim_fund
        WHERE morningstar_code IS NOT NULL
        {status_filter}
        """
    ).fetchall()

    scope = "all" if args.all else "active"
    print(f"Fetching prices for {len(funds)} {scope} fund(s) with Morningstar codes...")
    for fund_id, fund_name, ms_code in funds:
        start = get_fetch_start(con, fund_id, backfill_from)
        if start >= today:
            print(f"  {fund_name}: up to date")
            continue

        print(f"  {fund_name} ({ms_code}): fetching {start} to {today}")
        try:
            prices = fetch_morningstar_prices(ms_code, start, today)
        except requests.HTTPError as e:
            print(f"    ERROR: {e}")
            continue
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

        if not prices:
            print(f"    No price data returned — fund may need manual lookup")
            continue

        n = insert_fund_prices(con, fund_id, prices)
        print(f"    Inserted {n:,} rows")
        time.sleep(REQUEST_DELAY_SECONDS)

    # Warn about funds without Morningstar codes (same scope as the fetch above)
    missing = con.execute(
        f"""
        SELECT fund_id, fund_name FROM main.dim_fund
        WHERE morningstar_code IS NULL
        {status_filter}
        """
    ).fetchall()

    if missing:
        print(f"\nWARNING: {len(missing)} active fund(s) have no morningstar_code — prices cannot be fetched automatically:")
        for fund_id, name in missing:
            print(f"  [{fund_id}] {name}")
        print("  Add morningstar_code values to the funds table to enable price fetching.")

    # --- Benchmarks via yfinance ---
    print("\nFetching benchmark indices...")
    fetch_benchmarks(con, backfill_from)

    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
