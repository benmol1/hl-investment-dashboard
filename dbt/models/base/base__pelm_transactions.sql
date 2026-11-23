-- A table, not a view: the source is read from a relative file path, which a view would
-- re-resolve against whatever directory later queries it from.
{{ config(materialized='table') }}

-- Ledger rows for the PELM Will Trust, produced by backend/scripts/parse_pelm_ledger.py.
-- amount_gbp is the cash effect on the ledger: positive in, negative out, null if none.
select
    tx_date,
    nullif(reference, '')           as reference,
    tx_type,
    coalesce(security, '')          as security,
    quantity,
    amount_gbp,
    coalesce(notes, '')             as notes

from ({{ pelm_transactions_source() }}) as pelm_ledger
