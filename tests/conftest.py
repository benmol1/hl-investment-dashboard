import os
import pytest
import duckdb
from fastapi.testclient import TestClient

# Set JWT_SECRET before importing anything from the app so auth.py can be
# imported without raising RuntimeError.  The tests override the auth
# dependencies entirely, so this value is never used for real signing.
os.environ.setdefault("JWT_SECRET", "test-secret-for-testing-only")

from app.main import app
from app.db import get_db
from app.auth import CurrentUser, get_current_user, get_user_accounts


def _create_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE dim_date (
            date_key   INTEGER PRIMARY KEY,
            date       DATE,
            month_end_indicator VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_user (
            user_key     VARCHAR PRIMARY KEY,
            user_id      VARCHAR,
            username     VARCHAR,
            role         VARCHAR,
            display_name VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_provider (
            provider_key  VARCHAR PRIMARY KEY,
            provider_id   VARCHAR,
            provider_name VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_account (
            account_key  INTEGER PRIMARY KEY,
            account_name VARCHAR,
            account_type VARCHAR,
            user_id      VARCHAR,
            provider_id  VARCHAR,
            user_key     VARCHAR,
            provider_key VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_fund (
            fund_key                      INTEGER PRIMARY KEY,
            fund_id                       VARCHAR,
            fund_name                     VARCHAR,
            fund_short_name               VARCHAR,
            morningstar_code              VARCHAR,
            investment_status_indicator   VARCHAR,
            first_investment_date         DATE
        )
    """)
    con.execute("""
        CREATE TABLE dim_transaction_type (
            transaction_type_key INTEGER PRIMARY KEY,
            transaction_type     VARCHAR,
            transaction_subtype  VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE mart_portfolio_value_daily (
            valuation_date      DATE,
            account_name        VARCHAR,
            portfolio_value_gbp DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE fct_holdings_daily (
            date_key       INTEGER,
            fund_key       INTEGER,
            account_key    INTEGER,
            holding_type   VARCHAR,
            units_held     DOUBLE,
            fund_price_gbp DOUBLE,
            value_gbp      DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE mart_portfolio_inflows_daily (
            valuation_date          DATE,
            account_name            VARCHAR,
            portfolio_value_gbp     DOUBLE,
            cumulative_inflows_gbp  DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE mart_contributions_by_financial_year (
            account_name      VARCHAR,
            account_type      VARCHAR,
            financial_year    VARCHAR,
            contributions_gbp DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE mart_portfolio_returns_monthly (
            month_end_date              DATE,
            account_name                VARCHAR,
            monthly_return              DOUBLE,
            prev_month_end_value_gbp    DOUBLE,
            month_inflows_gbp           DOUBLE,
            trailing_12m_sharpe         DOUBLE,
            trailing_36m_sharpe         DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE mart_benchmarks_monthly (
            index_id            VARCHAR,
            month_end_date      DATE,
            month_end_level     DOUBLE,
            year_month          VARCHAR,
            trailing_12m_sharpe DOUBLE,
            trailing_36m_sharpe DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE mart_holdings_latest (
            fund_name           VARCHAR,
            account_name        VARCHAR,
            units_held          DOUBLE,
            fund_price_gbp      DOUBLE,
            value_gbp           DOUBLE,
            cost_basis_gbp      DOUBLE,
            unrealised_gain_gbp DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE fct_cash_position_daily (
            account_key       INTEGER,
            date_key          INTEGER,
            cash_balance_gbp  DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE ingest_log (
            source        VARCHAR,
            status        VARCHAR,
            rows_inserted INTEGER,
            run_at        TIMESTAMP
        )
    """)
    con.execute("CREATE TABLE transactions (trade_date DATE)")
    con.execute("CREATE TABLE prices (date DATE)")
    con.execute("""
        CREATE TABLE int_fund_values_daily (
            date_key       INTEGER,
            fund_key       INTEGER,
            fund_price_gbp DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE fct_transactions (
            transaction_id          VARCHAR,
            account_key             INTEGER,
            fund_key                INTEGER,
            transaction_type_key    INTEGER,
            trade_date_key          INTEGER,
            settle_date_key         INTEGER,
            transaction_reference   VARCHAR,
            quantity                DOUBLE,
            value_gbp               DOUBLE
        )
    """)


def _seed_data(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        INSERT INTO dim_date VALUES
        (1, '2024-01-31', 'Month End'),
        (2, '2024-02-29', 'Month End')
    """)
    con.execute("""
        INSERT INTO dim_user VALUES
        ('user_key_owner', 'owner', 'owner', 'owner', NULL)
    """)
    con.execute("""
        INSERT INTO dim_provider VALUES
        ('provider_key_hl', 'HL', 'Hargreaves Lansdown')
    """)
    con.execute("""
        INSERT INTO dim_account VALUES
        (1, 'ISA',  'ISA',  'owner', 'HL', 'user_key_owner', 'provider_key_hl'),
        (2, 'SIPP', 'SIPP', 'owner', 'HL', 'user_key_owner', 'provider_key_hl')
    """)
    con.execute("""
        INSERT INTO dim_fund VALUES
        (1, 'FUND_A', 'Fund Alpha', 'Alpha', 'MS001', 'Holding',  '2020-01-01'),
        (2, 'FUND_B', 'Fund Beta',  'Beta',  'MS002', 'Divested', '2019-01-01')
    """)
    con.execute("""
        INSERT INTO dim_transaction_type VALUES
        (1, 'BUY',          'Market'),
        (2, 'SELL',         'Market'),
        (3, 'CONTRIBUTION', NULL)
    """)
    con.execute("""
        INSERT INTO mart_portfolio_value_daily VALUES
        ('2024-01-31', 'ISA',  10000.0),
        ('2024-01-31', 'SIPP',  5000.0),
        ('2024-02-29', 'ISA',  10500.0),
        ('2024-02-29', 'SIPP',  5200.0)
    """)
    con.execute("""
        INSERT INTO fct_holdings_daily VALUES
        (1, 1, 1, 'Fund', 100.0, 50.0, 5000.0),
        (1, 1, 2, 'Fund',  50.0, 50.0, 2500.0),
        (2, 1, 1, 'Fund', 105.0, 52.0, 5460.0),
        (2, 1, 2, 'Fund',  52.0, 52.0, 2704.0)
    """)
    con.execute("""
        INSERT INTO mart_portfolio_inflows_daily VALUES
        ('2024-01-31', 'ISA',  10000.0, 8000.0),
        ('2024-01-31', 'SIPP',  5000.0, 4500.0),
        ('2024-02-29', 'ISA',  10500.0, 8500.0),
        ('2024-02-29', 'SIPP',  5200.0, 4700.0)
    """)
    con.execute("""
        INSERT INTO mart_contributions_by_financial_year VALUES
        ('ISA',  'ISA',  '2023/24', 5000.0),
        ('SIPP', 'SIPP', '2023/24', 3000.0),
        ('ISA',  'ISA',  '2024/25', 2000.0),
        ('SIPP', 'SIPP', '2024/25', 1500.0)
    """)
    con.execute("""
        INSERT INTO mart_portfolio_returns_monthly VALUES
        ('2024-01-31', 'ISA',  0.01,  9900.0,  0.0,   0.5,  0.4),
        ('2024-01-31', 'SIPP', 0.015, 4900.0,  0.0,   0.4,  0.3),
        ('2024-02-29', 'ISA',  0.02,  10000.0, 100.0, 0.6,  NULL),
        ('2024-02-29', 'SIPP', 0.01,  5000.0,   50.0, 0.5,  NULL)
    """)
    con.execute("""
        INSERT INTO mart_benchmarks_monthly VALUES
        ('FTSE100', '2024-01-31', 7500.0, '2024-01', 0.30, 0.25),
        ('FTSE100', '2024-02-29', 7600.0, '2024-02', 0.35, NULL),
        ('SP500',   '2024-01-31', 4800.0, '2024-01', 0.50, 0.40),
        ('SP500',   '2024-02-29', 4900.0, '2024-02', 0.55, NULL),
        ('NASDAQ',  '2024-01-31', 15000.0,'2024-01', 0.60, 0.50),
        ('NASDAQ',  '2024-02-29', 15500.0,'2024-02', 0.65, NULL)
    """)
    con.execute("""
        INSERT INTO mart_holdings_latest VALUES
        ('Fund Alpha', 'ISA',  105.0, 52.0, 5460.0, 4500.0, 960.0),
        ('Fund Alpha', 'SIPP',  52.0, 52.0, 2704.0, 2200.0, 504.0)
    """)
    con.execute("""
        INSERT INTO fct_cash_position_daily VALUES
        (1, 2, 500.0),
        (2, 2, 250.0)
    """)
    con.execute("""
        INSERT INTO ingest_log VALUES
        ('transactions', 'success', 10, '2024-02-29 10:00:00'),
        ('prices',       'success',  5, '2024-02-29 11:00:00')
    """)
    con.execute("INSERT INTO transactions VALUES ('2024-02-15')")
    con.execute("INSERT INTO prices VALUES ('2024-02-29')")
    con.execute("""
        INSERT INTO int_fund_values_daily VALUES
        (1, 1, 50.0),
        (2, 1, 52.0)
    """)
    con.execute("""
        INSERT INTO fct_transactions VALUES
        ('TX001', 1, 1, 1, 1, 2,    'REF001', 10.0, 500.0),
        ('TX002', 2, 1, 3, 1, NULL, 'REF002', NULL, 100.0),
        ('TX003', 1, 1, 2, 2, NULL, 'REF003',  5.0, 250.0)
    """)


@pytest.fixture(scope="session")
def db():
    con = duckdb.connect(":memory:")
    _create_schema(con)
    _seed_data(con)
    yield con
    con.close()


@pytest.fixture
def client(db):
    def _get_db_override():
        yield db

    # Bypass JWT authentication — tests use a fixed owner identity with
    # access to both ISA and SIPP accounts, matching the seed data above.
    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_current_user] = lambda: CurrentUser("owner", "owner")
    app.dependency_overrides[get_user_accounts] = lambda: frozenset(["ISA", "SIPP"])
    yield TestClient(app)
    app.dependency_overrides.clear()
