with daily as (
    select
        account_id,
        trade_date              as date,
        sum(value_gbp)          as contributed_today
    from {{ ref('stg_transactions') }}
    where is_contribution
    group by account_id, trade_date
)

select
    account_id,
    date,
    contributed_today,
    round(
        sum(contributed_today) over (
            partition by account_id
            order by date
        ),
        2
    ) as cumulative_contributions_gbp

from daily
