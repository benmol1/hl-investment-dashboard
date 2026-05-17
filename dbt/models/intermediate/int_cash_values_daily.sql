with account_date_spine as (
    select
        da.account_key,
        dd.date_key
    from {{ ref('dim_account') }} da
    inner join {{ ref('dim_date') }} dd
        on  dd.date >= da.account_open_date
        and dd.date <= current_date
)

select
    ads.date_key,
    ads.account_key,
    coalesce(cp.cash_balance_gbp, 0) as value_gbp
from account_date_spine ads
asof left join {{ ref('fct_cash_position_daily') }} cp
    on  cp.account_key = ads.account_key
    and cp.date_key   <= ads.date_key
