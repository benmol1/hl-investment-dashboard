select
    da.account_key,
    df.fund_key,
    v.account_id,
    v.fund_id,
    v.fund_name,
    v.valuation_date,
    v.units_held,
    v.price_gbp,
    v.value_gbp

from {{ ref('int_daily_fund_values') }} v
left join {{ ref('dim_account') }} da on da.account_name = v.account_id
left join {{ ref('dim_fund') }}    df on df.fund_id    = v.fund_id

-- TODO: check wheter we actually need this file, or whether we'd rather handle this information via a different route.
