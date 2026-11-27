-- Barratt & Cooke's reported total return for each report period alongside the dashboard's own
-- figure: the monthly Modified Dietz returns for the same months, geometrically linked. B&C
-- chain-link daily returns instead, so expect small differences (a few hundredths of a percent);
-- assert_pelm_reported_returns_reconcile fails the build if a fully covered period is off by more.
with reported as (
    select
        period_start,
        period_end,
        reported_return,
        source,
        -- Number of calendar months the period spans.
        datediff('month', period_start, period_end) + 1           as months_in_period
    from {{ ref('base__pelm_reported_returns') }}
),

dashboard as (
    select
        r.period_start,
        count(m.monthly_return)                                     as months_found,
        exp(sum(ln(1 + m.monthly_return))) - 1                      as dashboard_return,
        sum(-m.month_inflows_gbp)                                   as net_outflows_gbp,
        bool_and(m.cash_flow_coverage_indicator = 'Complete')       as all_months_complete
    from reported r
    inner join {{ ref('mart_portfolio_returns_monthly') }} m
        on  m.account_name = 'PELM'
        and last_day(cast(m.year_month || '-01' as date)) between r.period_start and r.period_end
    group by r.period_start
)

select
    r.period_start,
    r.period_end,
    r.source,
    r.reported_return,
    d.dashboard_return,
    round((d.dashboard_return - r.reported_return) * 100, 4)      as difference_pp,
    r.months_in_period,
    coalesce(d.months_found, 0)                                     as months_found,
    d.net_outflows_gbp,
    case
        when coalesce(d.months_found, 0) < r.months_in_period then 'Missing months'
        when d.all_months_complete                             then 'Complete'
        else 'Incomplete'
    end                                                             as cash_flow_coverage_indicator
from reported r
left join dashboard d on d.period_start = r.period_start
order by r.period_start
