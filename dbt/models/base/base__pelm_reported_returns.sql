-- A table, not a view: the source is read from a relative file path.
{{ config(materialized='table') }}

-- Total returns as reported by Barratt & Cooke in their formal performance reports, typed in by
-- hand from each report's header line. The reference the dashboard's own returns are checked
-- against (mart_pelm_return_reconciliation).
select
    period_start,
    period_end,
    return_pct / 100.0          as reported_return,
    coalesce(source, '')        as source

from ({{ pelm_reported_returns_source() }}) as reported
