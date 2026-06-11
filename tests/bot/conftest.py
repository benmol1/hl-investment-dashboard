import os

import duckdb
import pytest

# Set required env vars before any bot module is imported during collection.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


def _build_mini_warehouse(con: duckdb.DuckDBPyConnection) -> None:
    """A small star schema with hand-checkable numbers, covering every table
    the semantic layer definitions reference."""
    con.execute("""
        CREATE TABLE dim_date AS
        SELECT CAST(strftime(range, '%Y%m%d') AS INTEGER) AS date_key,
               CAST(range AS DATE)                        AS date
        FROM range(DATE '2025-01-01', DATE '2026-07-01', INTERVAL 1 DAY)
    """)
    con.execute("""
        CREATE TABLE dim_account (account_key VARCHAR, account_name VARCHAR);
        INSERT INTO dim_account VALUES ('A1', 'ISA'), ('A2', 'SIPP');
    """)
    con.execute("""
        CREATE TABLE dim_fund (
            fund_key VARCHAR, fund_id VARCHAR, fund_name VARCHAR,
            investment_status_indicator VARCHAR
        );
        INSERT INTO dim_fund VALUES
            ('F1', 'ISIN1', 'Fund Alpha', 'Holding'),
            ('F2', 'ISIN2', 'Fund Beta',  'Exited');
    """)
    con.execute("""
        CREATE TABLE dim_transaction_type (
            transaction_type_key INTEGER, transaction_type VARCHAR,
            contribution_indicator VARCHAR
        );
        INSERT INTO dim_transaction_type VALUES
            (1, 'BUY',          'Non-Contribution'),
            (2, 'CONTRIBUTION', 'Contribution'),
            (3, 'FEE',          'Non-Contribution'),
            (4, 'TRANSFER',     'Transfer'),
            (5, 'SELL',         'Non-Contribution');
    """)
    con.execute("""
        CREATE TABLE fct_transactions (
            transaction_id VARCHAR, account_key VARCHAR, fund_key VARCHAR,
            transaction_type_key INTEGER, trade_date_key INTEGER,
            quantity DOUBLE, value_gbp DOUBLE
        );
        INSERT INTO fct_transactions VALUES
            ('T1', 'A1', NULL, 2, 20250410, NULL,  1000.0),  -- ISA contribution FY26
            ('T2', 'A1', NULL, 2, 20250310, NULL,   500.0),  -- ISA contribution FY25
            ('T3', 'A2', NULL, 2, 20250501, NULL,  2000.0),  -- SIPP contribution FY26
            ('T4', 'A2', NULL, 4, 20250502, NULL,  3000.0),  -- SIPP transfer FY26
            ('T5', 'A1', 'F1', 1, 20250412, 80.0,  -800.0),  -- ISA buy Fund Alpha
            ('T6', 'A1', NULL, 3, 20250430, NULL,   -10.0),  -- ISA fee Apr-25
            ('T7', 'A1', NULL, 3, 20250630, NULL,    -5.0),  -- ISA fee Jun-25
            ('T8', 'A2', NULL, 3, 20250430, NULL,    -2.0);  -- SIPP fee Apr-25
    """)
    con.execute("""
        CREATE TABLE fct_holdings_daily (
            account_key VARCHAR, fund_key VARCHAR, date_key INTEGER,
            holding_type VARCHAR, units_held DOUBLE, value_gbp DOUBLE
        );
        INSERT INTO fct_holdings_daily VALUES
            ('A1', 'F1', 20250430, 'Fund', 80.0, 800.0),
            ('A1', 'F1', 20250531, 'Fund', 80.0, 880.0),
            ('A1', NULL, 20250430, 'Cash', NULL, 100.0),
            ('A1', NULL, 20250531, 'Cash', NULL, 200.0),
            ('A2', 'F2', 20250430, 'Fund', 50.0, 100.0),
            ('A2', 'F2', 20250531, 'Fund', 50.0, 110.0);
    """)
    con.execute("""
        CREATE TABLE mart_holdings_latest (
            account_name VARCHAR, holding_type VARCHAR, fund_name VARCHAR,
            units_held DOUBLE, value_gbp DOUBLE, cost_basis_gbp DOUBLE,
            unrealised_gain_gbp DOUBLE, weight_pct DOUBLE
        );
        INSERT INTO mart_holdings_latest VALUES
            ('ISA',  'Fund', 'Fund Alpha', 80.0, 880.0, 800.0,  80.0, 81.5),
            ('ISA',  'Cash', NULL,         NULL, 200.0,   0.0,  NULL, 18.5),
            ('SIPP', 'Fund', 'Fund Beta',  50.0, 105.0, 100.0,   5.0, 100.0);
    """)
    con.execute("""
        CREATE TABLE mart_portfolio_inflows_daily (
            account_name VARCHAR, valuation_date DATE,
            portfolio_value_gbp DOUBLE, inflows_gbp DOUBLE,
            cumulative_inflows_gbp DOUBLE
        );
        INSERT INTO mart_portfolio_inflows_daily VALUES
            ('ISA',  '2025-04-30',  900.0, 1000.0, 1500.0),
            ('ISA',  '2025-05-31', 1080.0,    0.0, 1500.0),
            ('SIPP', '2025-04-30',  100.0,    0.0, 5000.0),
            ('SIPP', '2025-05-31',  110.0,    0.0, 5000.0);
    """)
    con.execute("""
        CREATE TABLE mart_portfolio_returns_monthly (
            account_name VARCHAR, year_month VARCHAR, financial_year VARCHAR,
            month_end_date DATE, month_end_value_gbp DOUBLE,
            month_inflows_gbp DOUBLE, monthly_return DOUBLE,
            trailing_12m_return DOUBLE, trailing_36m_return_annualised DOUBLE,
            trailing_12m_sharpe DOUBLE, trailing_36m_sharpe DOUBLE
        );
        INSERT INTO mart_portfolio_returns_monthly VALUES
            ('ISA',  '2025-04', 'FY26', '2025-04-30',  900.0, 1000.0, 0.02, 0.10, 0.08, 1.1, 0.9),
            ('ISA',  '2025-05', 'FY26', '2025-05-31', 1080.0,    0.0, 0.03, 0.12, NULL, NULL, NULL),
            ('SIPP', '2025-05', 'FY26', '2025-05-31',  110.0,    0.0, 0.01, 0.05, NULL, 0.6, NULL);
    """)
    con.execute("""
        CREATE TABLE mart_benchmarks_monthly (
            index_id VARCHAR, year_month VARCHAR, month_end_date DATE,
            month_end_level DOUBLE, monthly_return DOUBLE,
            trailing_12m_return DOUBLE, trailing_36m_return_annualised DOUBLE,
            trailing_12m_sharpe DOUBLE, trailing_36m_sharpe DOUBLE
        );
        INSERT INTO mart_benchmarks_monthly VALUES
            ('FTSE100', '2025-05', '2025-05-30', 8000.0,  0.01, 0.07, 0.05, 0.8, 0.7),
            ('SP500',   '2025-05', '2025-05-30', 5500.0,  0.02, 0.15, 0.11, 1.4, 1.2),
            ('NASDAQ',  '2025-05', '2025-05-30', 19000.0, 0.03, 0.20, 0.15, 1.6, 1.3);
    """)


@pytest.fixture(scope="session")
def warehouse_path(tmp_path_factory):
    """Path to a DuckDB file containing the mini star-schema warehouse."""
    path = tmp_path_factory.mktemp("warehouse") / "test_warehouse.duckdb"
    con = duckdb.connect(str(path))
    try:
        _build_mini_warehouse(con)
    finally:
        con.close()
    return path


@pytest.fixture(scope="session")
def warehouse(warehouse_path):
    """Read-only connection to the mini warehouse."""
    con = duckdb.connect(str(warehouse_path), read_only=True)
    yield con
    con.close()
