-- A table, not a view: the source is read from a relative file path.
{{ config(materialized='table') }}

-- One row per Barratt & Cooke ledger statement that was parsed: which sub-ledger, and the period
-- it covers. Written by backend/scripts/parse_pelm_ledger.py alongside pelm_transactions.csv.
select
    ledger,
    period_start,
    period_end,
    opening_gbp,
    closing_gbp,
    coalesce(source_file, '') as source_file

from ({{ pelm_ledger_coverage_source() }}) as coverage
