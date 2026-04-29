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

-- ---------------------------------------------------------------------------
-- Analytical views
-- ---------------------------------------------------------------------------

-- Running unit balance per fund per day across all accounts
CREATE OR REPLACE VIEW v_holdings AS
WITH daily_moves AS (
    SELECT
        fund_id,
        trade_date AS date,
        -- value_gbp < 0 = money out = units acquired; value_gbp > 0 = money in = units disposed
        SUM(CASE WHEN value_gbp < 0 THEN quantity ELSE -quantity END) AS unit_delta
    FROM transactions
    WHERE transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
      AND fund_id IS NOT NULL
      AND quantity IS NOT NULL
    GROUP BY fund_id, trade_date
)
SELECT
    d.date,
    m.fund_id,
    SUM(m.unit_delta) OVER (
        PARTITION BY m.fund_id
        ORDER BY d.date
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS units_held
FROM dim_date d
JOIN daily_moves m ON m.date <= d.date
WHERE d.date >= (SELECT MIN(trade_date) FROM transactions);

-- Portfolio value over time (requires prices to be loaded)
CREATE OR REPLACE VIEW v_portfolio_value AS
SELECT
    h.date,
    h.fund_id,
    f.name AS fund_name,
    h.units_held,
    p.price_pence,
    ROUND(h.units_held * p.price_pence / 100.0, 2) AS value_gbp
FROM v_holdings h
JOIN funds f ON f.id = h.fund_id
JOIN prices p ON p.fund_id = h.fund_id AND p.date = h.date
WHERE h.units_held > 0.0001;

-- Cumulative contributions vs portfolio value (for growth breakdown)
CREATE OR REPLACE VIEW v_contributions_vs_value AS
SELECT
    d.date,
    COALESCE(SUM(t.value_gbp) OVER (ORDER BY d.date ROWS UNBOUNDED PRECEDING), 0) AS cumulative_contributions,
    COALESCE(pv.total_value, 0) AS portfolio_value
FROM dim_date d
LEFT JOIN transactions t
    ON t.trade_date = d.date
    AND t.transaction_type = 'CONTRIBUTION'
LEFT JOIN (
    SELECT date, SUM(value_gbp) AS total_value
    FROM v_portfolio_value
    GROUP BY date
) pv ON pv.date = d.date;
