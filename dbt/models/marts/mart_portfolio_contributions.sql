with cumulative_contribs as (
    -- Compute running total on the contribution date spine, independent of
    -- portfolio value dates. This ensures contributions made before the first
    -- fund price (e.g. a transfer-in that settles before any holdings appear)
    -- are captured when we join to portfolio dates below.
    select
        account_id,
        contribution_date,
        contributed_today,
        sum(contributed_today) over (
            partition by account_id
            order by contribution_date
            rows between unbounded preceding and current row
        ) as cumulative_contributions_gbp
    from {{ ref('int_daily_contributions') }}
)

select
    pv.account_id,
    pv.valuation_date,
    pv.portfolio_value_gbp,
    coalesce(dc.contributed_today, 0)          as contributions_gbp,
    coalesce(cc.cumulative_contributions_gbp, 0) as cumulative_contributions_gbp

from {{ ref('mart_daily_portfolio_value') }} pv
left join {{ ref('int_daily_contributions') }} dc
    on  dc.account_id        = pv.account_id
    and dc.contribution_date = pv.valuation_date
asof left join cumulative_contribs cc
    on  pv.account_id         = cc.account_id
    and pv.valuation_date     >= cc.contribution_date
