-- PELM ledger lines with a category, so consumers can tell real activity from internal cash
-- sweeps and from money that crossed the trust's boundary.
select
    {{ dbt_utils.generate_surrogate_key(['reference', 'tx_type', 'security']) }} as transaction_id,
    tx_date,
    strftime(tx_date, '%Y-%m')                                                  as year_month,
    reference,
    tx_type,
    case
        when tx_type in ('BUY', 'SELL')                                      then 'trade'
        when tx_type in ('CASH_TRANSFER_IN', 'WITHDRAWAL', 'STOCK_TRANSFER_IN') then 'external_flow'
        when tx_type in ('DEPOSIT_TRANSFER_IN', 'DEPOSIT_TRANSFER_OUT')      then 'internal_transfer'
        when tx_type in ('CORPORATE_ACTION', 'CASH_FRACTION')                then 'corporate_action'
        when tx_type = 'OPENING_BALANCE'                                     then 'opening_balance'
        else 'other'
    end                                                                         as category,
    security,
    quantity,
    amount_gbp,
    notes

from {{ ref('base__pelm_transactions') }}
