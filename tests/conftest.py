import pytest
import duckdb
from fastapi.testclient import TestClient

from app.main import app
from app.db import get_db


def _create_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE dim_date (
            date_key   INTEGER PRIMARY KEY,
            date       DATE,
            month_end_indicator VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE dim_account (
            account_key  INTEGER PRIMARY KEY,
            account_name VARCHAR,
            data_grain   VARCHAR
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
            financial_year    VARCHAR,
            account_name      VARCHAR,
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
            trailing_36m_sharpe         DOUBLE,
            cash_flow_coverage_indicator VARCHAR DEFAULT 'Complete'
        )
    """)
    con.execute("""
        CREATE TABLE mart_portfolio_snapshot_monthly (
            account_name        VARCHAR,
            month_end_date      DATE,
            month_end_value_gbp DOUBLE,
            cash_balance_gbp    DOUBLE,
            invested_value_gbp  DOUBLE
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
            holding_type        VARCHAR,    
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
        CREATE TABLE fct_pelm_transactions (
            transaction_id VARCHAR,
            tx_date        DATE,
            year_month     VARCHAR,
            reference      VARCHAR,
            tx_type        VARCHAR,
            category       VARCHAR,
            security       VARCHAR,
            quantity       DOUBLE,
            amount_gbp     DOUBLE,
            notes          VARCHAR,
            ledger         VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE mart_pelm_income_monthly (
            year_month                VARCHAR,
            month_end_date            DATE,
            month_end_value_gbp       DOUBLE,
            dividends_gbp             DOUBLE,
            interest_gbp              DOUBLE,
            income_gbp                DOUBLE,
            fx_commission_gbp         DOUBLE,
            custody_fees_gbp          DOUBLE,
            income_distributed_gbp    DOUBLE,
            income_coverage_indicator VARCHAR,
            fees_coverage_indicator   VARCHAR,
            trailing_12m_income_gbp   DOUBLE,
            trailing_12m_income_yield DOUBLE
        )
    """)
    con.execute("""
        CREATE TABLE mart_pelm_return_reconciliation (
            period_start                 DATE,
            period_end                   DATE,
            source                       VARCHAR,
            reported_return              DOUBLE,
            dashboard_return             DOUBLE,
            difference_pp                DOUBLE,
            months_in_period             INTEGER,
            months_found                 INTEGER,
            net_outflows_gbp             DOUBLE,
            cash_flow_coverage_indicator VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE base__pelm_ledger_coverage (
            ledger       VARCHAR,
            period_start DATE,
            period_end   DATE,
            opening_gbp  DOUBLE,
            closing_gbp  DOUBLE,
            source_file  VARCHAR
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
        INSERT INTO dim_account VALUES
        (1, 'ISA',  'daily'),
        (2, 'SIPP', 'daily'),
        (3, 'PELM', 'monthly')
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
        ('2023/24', 'ISA',  5000.0),
        ('2023/24', 'SIPP', 3000.0),
        ('2024/25', 'ISA',  2000.0),
        ('2024/25', 'SIPP', 1500.0)
    """)
    con.execute("""
        INSERT INTO mart_portfolio_returns_monthly VALUES
        ('2024-01-31', 'ISA',  0.01,  9900.0,  0.0,   0.5,  0.4,  'Complete'),
        ('2024-01-31', 'SIPP', 0.015, 4900.0,  0.0,   0.4,  0.3,  'Complete'),
        ('2024-02-29', 'ISA',  0.02,  10000.0, 100.0, 0.6,  NULL, 'Complete'),
        ('2024-02-29', 'SIPP', 0.01,  5000.0,   50.0, 0.5,  NULL, 'Complete'),
        ('2024-01-31', 'PELM', 0.05,  1000.0,    0.0,   0.9,  0.8,  'Complete'),
        ('2024-02-29', 'PELM', 0.10,  1050.0,    0.0,   0.9,  NULL, 'Incomplete')
    """)
    # Best estimate: actual return, plus a 1% income uplift on months with incomplete flows.
    con.execute("""
        ALTER TABLE mart_portfolio_returns_monthly ADD COLUMN estimated_monthly_return DOUBLE
    """)
    con.execute("""
        UPDATE mart_portfolio_returns_monthly
        SET estimated_monthly_return = monthly_return
            + CASE WHEN cash_flow_coverage_indicator = 'Incomplete' THEN 0.01 ELSE 0 END
    """)
    con.execute("""
        INSERT INTO mart_portfolio_snapshot_monthly VALUES
        ('PELM', '2023-12-31', 1000.0, NULL,  NULL),
        ('PELM', '2024-01-31', 1050.0, 200.0, 850.0),
        ('PELM', '2024-02-29', 1155.0, 300.0, 855.0),
        ('PELM', '2024-03-31', NULL,   NULL,  NULL)
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
        ('Fund Alpha', 'Fund', 'ISA',  105.0, 52.0, 5460.0, 4500.0, 960.0),
        ('Fund Alpha', 'Fund', 'SIPP',  52.0, 52.0, 2704.0, 2200.0, 504.0),
        -- Cash rows have no fund and no cost basis, as in the real mart
        (NULL, 'Cash', 'ISA',  NULL, NULL,  500.0, NULL, NULL),
        (NULL, 'Cash', 'SIPP', NULL, NULL,  250.0, NULL, NULL)
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
        INSERT INTO fct_pelm_transactions VALUES
        ('P1', '2024-01-10', '2024-01', 'B1', 'BUY',                'trade',            'ACME PLC',  10.0, -500.0, '', 'capital'),
        ('P2', '2024-01-15', '2024-01', 'S1', 'SELL',               'trade',            'ACME PLC',   4.0,  250.0, '', 'capital'),
        ('P3', '2024-01-20', '2024-01', 'T1', 'DEPOSIT_TRANSFER_OUT','internal_transfer','',        NULL, -250.0, '', 'capital'),
        ('P4', '2024-02-01', '2024-02', 'W1', 'WITHDRAWAL',         'external_flow',    '',          NULL, -1000.0, 'BACS Payment', 'capital'),
        ('P5', '2024-02-02', '2024-02', 'X1', 'STOCK_TRANSFER_IN',  'external_flow',    'OLD CO',   50.0, NULL, 'in specie', 'capital')
    """)
    con.execute("""
        INSERT INTO mart_pelm_income_monthly VALUES
        ('2023-12', '2023-12-31', 1000.0,  0.0,  0.0,  0.0, 0.0,  0.0,  0.0, 'Incomplete', 'Incomplete', NULL, NULL),
        ('2024-01', '2024-01-31', 1050.0, 10.0,  1.0, 11.0, 0.1, 90.0, 12.0, 'Complete',   'Complete',   NULL, NULL),
        ('2024-02', '2024-02-29', 1155.0, 20.0,  0.0, 20.0, 0.2,  0.0, 15.0, 'Complete',   'Incomplete', NULL, NULL),
        ('2024-03', '2024-03-31', 1160.0, 30.0,  2.0, 32.0, 0.3,  0.0, 25.0, 'Complete',   'Incomplete', NULL, NULL),
        ('2024-04', '2024-04-30', 1170.0,  0.0,  0.0,  0.0, 0.0,  0.0,  0.0, 'Incomplete', 'Incomplete', NULL, NULL)
    """)
    con.execute("""
        INSERT INTO mart_pelm_return_reconciliation VALUES
        ('2024-01-01', '2024-03-31', 'Report to 31.3.24', 0.0448, 0.0450, 0.02, 3, 3, 52.0, 'Complete')
    """)
    con.execute("""
        INSERT INTO base__pelm_ledger_coverage VALUES
        ('capital',   '2023-12-01', '2024-02-29', 0.0, 0.0, 'a.pdf'),
        ('dividends', '2024-01-01', '2024-03-31', 0.0, 5.0, 'a.pdf')
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

    app.dependency_overrides[get_db] = _get_db_override
    yield TestClient(app)
    app.dependency_overrides.clear()
