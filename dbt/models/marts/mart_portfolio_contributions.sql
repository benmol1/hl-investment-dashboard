with joined as (
    select
        pv.account_id,
        pv.date,
        pv.portfolio_value_gbp,
        coalesce(dc.contributed_today, 0) as contributions_gbp
    from {{ ref('mart_daily_portfolio_value') }} pv
    left join {{ ref('int_daily_contributions') }} dc
        on  dc.account_id = pv.account_id
        and dc.contribution_date = pv.date
)

select
    account_id,
    date,
    portfolio_value_gbp,
    contributions_gbp,
    sum(contributions_gbp) over (
        partition by account_id
        order by date
        rows between unbounded preceding and current row
    ) as cumulative_contributions_gbp
from joined
