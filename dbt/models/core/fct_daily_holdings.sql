select
    da.account_key,
    df.fund_key,
    v.account_id,
    v.fund_id,
    v.fund_name,
    v.valuation_date,
    v.units_held,
    v.price_gbp,
    v.value_gbp,

    coalesce(cb.cost_basis_gbp, 0)               as cost_basis_gbp,
    v.value_gbp - coalesce(cb.cost_basis_gbp, 0) as unrealised_gain_gbp,

    case
        when coalesce(cb.cost_basis_gbp, 0) > 0
        then round(
            (v.value_gbp - cb.cost_basis_gbp) / cb.cost_basis_gbp * 100.0,
            2
        )
        else 0.0
    end as unrealised_gain_pct

from {{ ref('int_daily_fund_values') }} v
left join {{ ref('int_fund_cost_basis') }} cb
    on  cb.account_id = v.account_id
    and cb.fund_id    = v.fund_id
left join {{ ref('dim_account') }} da on da.account_name = v.account_id
left join {{ ref('dim_fund') }}    df on df.fund_id    = v.fund_id
