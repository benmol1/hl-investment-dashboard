-- Audit log written by ingest_transactions.py and fetch_prices.py on each run.
-- Used by the freshness indicator in the dashboard header.
CREATE TABLE IF NOT EXISTS ingest_log (
    run_at         TIMESTAMPTZ NOT NULL,
    source         TEXT        NOT NULL,  -- 'transactions' or 'prices'
    rows_inserted  INTEGER     NOT NULL DEFAULT 0,
    status         TEXT        NOT NULL,  -- 'success' or 'failure'
    detail         TEXT                   -- error message on failure, NULL on success
);
