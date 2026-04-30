select
    pv.account_id,
    pv.date,
    pv.portfolio_value_gbp,

    coalesce(dc.cumulative_contributions_gbp, 0) as cumulative_contributions_gbp,

    round(
        pv.portfolio_value_gbp - coalesce(dc.cumulative_contributions_gbp, 0),
        2
    ) as growth_gbp

from {{ ref('mart_daily_portfolio_value') }} pv
left join {{ ref('int_daily_contributions') }} dc
    on  dc.account_id = pv.account_id
    and dc.date       = pv.date
