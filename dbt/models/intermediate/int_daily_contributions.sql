select
    account_id,
    trade_date                   as contribution_date,
    sum(value_gbp)               as contributed_today
from {{ ref('stg_transactions') }}
where is_contribution
group by account_id, trade_date
