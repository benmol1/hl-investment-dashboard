-- HL Investment Dashboard — initial schema
-- Run via setup_db.py; safe to re-run (all CREATE IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS accounts (
    id    TEXT PRIMARY KEY,
    name  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS funds (
    id                TEXT PRIMARY KEY,  -- ISIN, or 'CASH' for cash positions
    name              TEXT NOT NULL,
    isin              TEXT,
    morningstar_code  TEXT,              -- e.g. '0P0000SVHO'; used to fetch NAV history
    currency          TEXT NOT NULL DEFAULT 'GBP',
    is_active         BOOLEAN NOT NULL DEFAULT TRUE
);

-- Date dimension — retained for easy financial-year grouping (Apr–Mar UK tax year)
CREATE TABLE IF NOT EXISTS dim_date (
    date            DATE PRIMARY KEY,
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    day             INTEGER NOT NULL,
    year_month      TEXT NOT NULL,    -- 'YYYY-MM'
    financial_year  TEXT NOT NULL     -- 'FY17', 'FY18', etc.
);

-- Lookup: named HL reference strings → transaction type
-- Patterned references (B..., BX..., X..., URIB...) are classified in Python code
CREATE TABLE IF NOT EXISTS transaction_type_mapping (
    reference_pattern   TEXT PRIMARY KEY,
    transaction_type    TEXT NOT NULL,
    transaction_subtype TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id                  TEXT PRIMARY KEY,  -- MD5 of (account_id|trade_date|reference|value_gbp)
    account_id          TEXT NOT NULL REFERENCES accounts(id),
    fund_id             TEXT REFERENCES funds(id),
    trade_date          DATE NOT NULL,
    settle_date         DATE,
    reference           TEXT NOT NULL,
    raw_description     TEXT,
    transaction_type    TEXT NOT NULL,
    transaction_subtype TEXT,
    unit_cost_pence     DOUBLE,  -- price per unit in pence; NULL for cash-only rows
    quantity            DOUBLE,  -- units; always positive; direction from value_gbp sign
    value_gbp           DOUBLE NOT NULL  -- negative = debit (buy/fee), positive = credit
);

CREATE TABLE IF NOT EXISTS prices (
    fund_id     TEXT NOT NULL REFERENCES funds(id),
    date        DATE NOT NULL,
    price_pence DOUBLE NOT NULL,  -- NAV in pence, consistent with HL raw data
    source      TEXT NOT NULL DEFAULT 'morningstar',
    PRIMARY KEY (fund_id, date)
);

CREATE TABLE IF NOT EXISTS benchmarks (
    index_id  TEXT NOT NULL,   -- 'FTSE100', 'SP500', 'NASDAQ'
    date      DATE NOT NULL,
    level     DOUBLE NOT NULL,
    ticker    TEXT,            -- Yahoo Finance ticker used to fetch
    PRIMARY KEY (index_id, date)
);

-- Analytical views were removed — they are now managed as dbt models:
--   v_holdings       → dbt/models/intermediate/int_daily_unit_balances.sql
--   v_portfolio_value → dbt/models/intermediate/int_daily_fund_values.sql
