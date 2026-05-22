"""
Generate a standalone demo DuckDB database with synthetic investment data.

The demo DB has the same schema as the production DB but contains entirely
fictional positions — safe to show to others without disclosing real holdings.

Usage:
    uv run python backend/scripts/generate_demo_data.py

After running, build the mart layer against the demo DB:
    cd dbt
    dbt seed --profiles-dir . --target demo
    dbt run  --profiles-dir . --target demo

Then start the backend against the demo DB:
    HL_DB_PATH=./data/hl_demo.duckdb uvicorn app.main:app --app-dir backend
"""

import hashlib
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEMO_DB_PATH = ROOT / "data" / "hl_demo.duckdb"
MIGRATIONS_DIR = ROOT / "backend" / "migrations"

RANDOM_SEED = 42

# Four invented funds: (id, name, short_name, morningstar_code, start_pence, daily_drift, daily_vol)
DEMO_FUNDS = [
    ("GB00DEMO0001", "Global Equity Tracker",   "Global Equity", "0P00DEMO001", 350.0, 0.00030, 0.012),
    ("GB00DEMO0002", "UK All-Share Tracker",     "UK All-Share",  "0P00DEMO002", 220.0, 0.00010, 0.010),
    ("GB00DEMO0003", "Emerging Markets Equity",  "EM Equity",     "0P00DEMO003", 180.0, 0.00020, 0.015),
    ("GB00DEMO0004", "Corporate Bond Fund",      "Corp Bonds",    "0P00DEMO004", 150.0, 0.00008, 0.005),
]

# Per-account allocation weights across the four funds (must sum to 1.0)
ISA_WEIGHTS  = [0.40, 0.30, 0.20, 0.10]
SIPP_WEIGHTS = [0.35, 0.25, 0.25, 0.15]

START_DATE = date(2022, 1, 1)
END_DATE   = date(2026, 4, 30)

MONTHLY_ISA_CONTRIBUTION  = 750.0
MONTHLY_SIPP_CONTRIBUTION = 300.0
BUY_RATIO = 0.95  # invest 95% of each contribution; 5% stays as cash residual

BENCHMARK_STARTS = {"FTSE100": 7250.0, "SP500": 4700.0, "NASDAQ": 15200.0}
BENCHMARK_PARAMS = {
    # (daily_drift, daily_vol, yahoo_ticker)
    "FTSE100": (0.00012, 0.009, "^FTSE"),
    "SP500":   (0.00030, 0.012, "^GSPC"),
    "NASDAQ":  (0.00040, 0.018, "^IXIC"),
}


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def _date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _is_weekday(d: date) -> bool:
    return d.weekday() < 5


def _last_weekday_of_month(y: int, m: int) -> date:
    if m == 12:
        last = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(y, m + 1, 1) - timedelta(days=1)
    while not _is_weekday(last):
        last -= timedelta(days=1)
    return last


def _add_working_days(d: date, n: int) -> date:
    added = 0
    while added < n:
        d += timedelta(days=1)
        if _is_weekday(d):
            added += 1
    return d


def _nearest_price_on_or_before(prices: dict, d: date) -> float | None:
    for i in range(10):
        candidate = d - timedelta(days=i)
        if candidate in prices:
            return prices[candidate]
    return None


# ---------------------------------------------------------------------------
# Synthetic price generation
# ---------------------------------------------------------------------------


def _generate_fund_prices() -> dict[str, dict[date, float]]:
    """Returns {fund_id: {date: price_pence}} for all weekdays in the range."""
    random.seed(RANDOM_SEED)
    all_prices: dict[str, dict[date, float]] = {}
    for fund_id, _, _, _, start_pence, drift, vol in DEMO_FUNDS:
        prices: dict[date, float] = {}
        price = start_pence
        for d in _date_range(START_DATE, END_DATE):
            price = max(price * (1 + drift + vol * random.gauss(0, 1)), 1.0)
            if _is_weekday(d):
                prices[d] = round(price, 2)
        all_prices[fund_id] = prices
    return all_prices


def _generate_benchmark_prices() -> dict[str, dict[date, float]]:
    """Returns {index_id: {date: level}} for FTSE100, SP500, NASDAQ."""
    bench: dict[str, dict[date, float]] = {}
    for index_id, (drift, vol, _) in BENCHMARK_PARAMS.items():
        prices: dict[date, float] = {}
        level = BENCHMARK_STARTS[index_id]
        for d in _date_range(START_DATE, END_DATE):
            level = max(level * (1 + drift + vol * random.gauss(0, 1)), 1.0)
            if _is_weekday(d):
                prices[d] = round(level, 2)
        bench[index_id] = prices
    return bench


# ---------------------------------------------------------------------------
# Synthetic transaction generation
# ---------------------------------------------------------------------------


def _make_tx_id(account_id: str, trade_date: date, reference: str, value_gbp: float) -> str:
    key = f"{account_id}|{trade_date}|{reference}|{value_gbp}"
    return hashlib.md5(key.encode()).hexdigest()


def _generate_transactions(fund_prices: dict) -> list[tuple]:
    """
    Returns a list of raw transaction tuples matching the transactions table schema:
    (id, account_id, fund_id, trade_date, settle_date, reference, raw_description,
     transaction_type, transaction_subtype, unit_cost_pence, quantity, value_gbp)
    """
    rows: list[tuple] = []
    buy_ref_counter = 10000

    accounts = [
        ("ISA",  MONTHLY_ISA_CONTRIBUTION,  ISA_WEIGHTS),
        ("SIPP", MONTHLY_SIPP_CONTRIBUTION, SIPP_WEIGHTS),
    ]

    y, m = START_DATE.year, START_DATE.month
    while True:
        contrib_date = date(y, m, 15)
        if not _is_weekday(contrib_date):
            # Move to the previous Friday
            while not _is_weekday(contrib_date):
                contrib_date -= timedelta(days=1)

        if contrib_date > END_DATE:
            break

        buy_date = _last_weekday_of_month(y, m)
        if buy_date > END_DATE:
            buy_date = END_DATE
            while not _is_weekday(buy_date):
                buy_date -= timedelta(days=1)

        for account_id, monthly_amount, weights in accounts:
            # CONTRIBUTION
            tx_id = _make_tx_id(account_id, contrib_date, "REG. SAVER", monthly_amount)
            rows.append((
                tx_id, account_id, None,
                contrib_date, None,
                "REG. SAVER", "Regular saver contribution",
                "CONTRIBUTION", "Regular",
                None, None, monthly_amount,
            ))

            # BUY per fund
            invest_total = monthly_amount * BUY_RATIO
            for i, (fund_id, fund_name, _, _, _, _, _) in enumerate(DEMO_FUNDS):
                amount = round(invest_total * weights[i], 2)
                price_pence = _nearest_price_on_or_before(fund_prices[fund_id], buy_date)
                if not price_pence:
                    continue

                quantity = round(amount / (price_pence / 100), 4)
                value_gbp = round(-amount, 2)  # negative = debit (cash out)
                buy_ref_counter += 1
                ref = f"B{buy_ref_counter}"
                settle = _add_working_days(buy_date, 3)
                desc = f"{fund_name} (GBP) {quantity} @  {price_pence:.6f}"

                tx_id = _make_tx_id(account_id, buy_date, ref, value_gbp)
                rows.append((
                    tx_id, account_id, fund_id,
                    buy_date, settle,
                    ref, desc,
                    "BUY", None,
                    price_pence, quantity, value_gbp,
                ))

        # Advance month
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1

    return rows


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------


def _run_migrations(con: duckdb.DuckDBPyConnection) -> None:
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        print(f"  Running migration: {sql_file.name}")
        con.execute(sql_file.read_text(encoding="utf-8"))


def _seed_reference_data(con: duckdb.DuckDBPyConnection) -> None:
    # Users: a single demo user owns all demo accounts
    con.execute("""
        INSERT OR IGNORE INTO users (id, username, hashed_password, role, display_name)
        VALUES ('demo', 'demo', NULL, 'demo', 'Demo User')
    """)

    # Provider
    con.execute("INSERT OR IGNORE INTO providers VALUES ('HL', 'Hargreaves Lansdown')")

    # Accounts: demo ISA and SIPP, owned by the demo user
    con.execute("""
        INSERT OR IGNORE INTO accounts (id, name, user_id, provider_id, account_type)
        VALUES
            ('ISA',  'Demo Stocks & Shares ISA',           'demo', 'HL', 'ISA'),
            ('SIPP', 'Demo Self-Invested Personal Pension', 'demo', 'HL', 'SIPP')
    """)

    # Funds
    for fund_id, name, short_name, ms_code, _, _, _ in DEMO_FUNDS:
        con.execute("""
            INSERT OR REPLACE INTO funds (id, name, isin, morningstar_code, short_name, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        """, (fund_id, name, fund_id, ms_code, short_name))

    print(f"  Seeded users, providers, accounts, {len(DEMO_FUNDS)} funds")


def _insert_prices(con: duckdb.DuckDBPyConnection, fund_prices: dict) -> None:
    rows = []
    for fund_id, dates in fund_prices.items():
        for d, price_pence in dates.items():
            rows.append((fund_id, d, price_pence))
    con.executemany(
        "INSERT OR IGNORE INTO prices (fund_id, date, price_pence) VALUES (?, ?, ?)",
        rows,
    )
    print(f"  Inserted {len(rows):,} price rows")


def _insert_benchmarks(con: duckdb.DuckDBPyConnection, bench_prices: dict) -> None:
    rows = []
    for index_id, dates in bench_prices.items():
        ticker = BENCHMARK_PARAMS[index_id][2]
        for d, level in dates.items():
            rows.append((index_id, d, level, ticker))
    con.executemany(
        "INSERT OR IGNORE INTO benchmarks (index_id, date, level, ticker) VALUES (?, ?, ?, ?)",
        rows,
    )
    print(f"  Inserted {len(rows):,} benchmark rows")


def _insert_transactions(con: duckdb.DuckDBPyConnection, transactions: list[tuple]) -> None:
    con.executemany("""
        INSERT OR IGNORE INTO transactions (
            id, account_id, fund_id,
            trade_date, settle_date,
            reference, raw_description,
            transaction_type, transaction_subtype,
            unit_cost_pence, quantity, value_gbp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, transactions)
    print(f"  Inserted {len(transactions):,} transactions")


def _seed_ingest_log(con: duckdb.DuckDBPyConnection) -> None:
    ts = datetime.now(timezone.utc)
    con.executemany(
        "INSERT INTO ingest_log (run_at, source, rows_inserted, status) VALUES (?, ?, ?, 'success')",
        [(ts, "transactions", 500), (ts, "prices", 5000)],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    DEMO_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DEMO_DB_PATH.exists():
        DEMO_DB_PATH.unlink()
        print(f"Removed existing demo DB: {DEMO_DB_PATH}")

    print(f"Creating demo database: {DEMO_DB_PATH}")
    con = duckdb.connect(str(DEMO_DB_PATH))

    print("Running migrations...")
    _run_migrations(con)

    print("Seeding reference data...")
    _seed_reference_data(con)

    print("Generating synthetic prices...")
    fund_prices = _generate_fund_prices()
    bench_prices = _generate_benchmark_prices()
    _insert_prices(con, fund_prices)
    _insert_benchmarks(con, bench_prices)

    print("Generating synthetic transactions...")
    transactions = _generate_transactions(fund_prices)
    _insert_transactions(con, transactions)

    _seed_ingest_log(con)

    con.close()
    print("\nDemo database ready.")
    print("\nNext steps:")
    print("  1. Build mart layer:")
    print("       cd dbt && dbt seed --profiles-dir . --target demo && dbt run --profiles-dir . --target demo")
    print("  2. Start the backend against the demo DB:")
    print("       HL_DB_PATH=./data/hl_demo.duckdb uvicorn app.main:app --app-dir backend")


if __name__ == "__main__":
    main()
