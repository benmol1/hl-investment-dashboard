-- Fix v_holdings: replace the buggy cross-join approach with ASOF JOIN,
-- which correctly forward-fills unit balances from trade dates to every calendar day.
-- Also drops the unused v_contributions_vs_value view (replaced by API query logic).

CREATE OR REPLACE VIEW v_holdings AS
WITH delta AS (
    SELECT
        fund_id,
        trade_date,
        SUM(CASE WHEN value_gbp < 0 THEN quantity ELSE -quantity END) AS unit_delta
    FROM transactions
    WHERE transaction_type IN ('BUY', 'SELL', 'SWITCH_IN', 'SWITCH_OUT')
      AND fund_id IS NOT NULL
      AND quantity IS NOT NULL
    GROUP BY fund_id, trade_date
),
running AS (
    SELECT
        fund_id,
        trade_date,
        SUM(unit_delta) OVER (PARTITION BY fund_id ORDER BY trade_date) AS units_held
    FROM delta
),
fund_dates AS (
    SELECT d.date, r.fund_id
    FROM dim_date d
    CROSS JOIN (SELECT DISTINCT fund_id FROM running) r
    WHERE d.date >= (SELECT MIN(trade_date) FROM running)
)
SELECT fd.date, fd.fund_id, r.units_held
FROM fund_dates fd
ASOF JOIN running r ON (fd.fund_id = r.fund_id AND fd.date >= r.trade_date);

CREATE OR REPLACE VIEW v_portfolio_value AS
SELECT
    h.date,
    h.fund_id,
    f.name AS fund_name,
    h.units_held,
    p.price_pence / 100.0 AS price_gbp,
    ROUND(h.units_held * p.price_pence / 100.0, 2) AS value_gbp
FROM v_holdings h
JOIN funds f ON f.id = h.fund_id
JOIN prices p ON p.fund_id = h.fund_id AND p.date = h.date
WHERE h.units_held > 0.0001;

DROP VIEW IF EXISTS v_contributions_vs_value;
