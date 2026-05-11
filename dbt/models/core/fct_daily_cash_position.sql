with daily_movements as (
    select
        dd.date_key,
        ft.account_key,
        sum(case when dtt.trade_indicator        = 'Trade'
                 then ft.value_gbp else 0 end)                                               as trade_cash_net_gbp,
        sum(case when dtt.contribution_indicator = 'Contribution'
                 then ft.value_gbp else 0 end)                                               as contributions_gbp,
        sum(case when dtt.trade_indicator        = 'Non-Trade'
                  and dtt.contribution_indicator = 'Non-Contribution'
                 then ft.value_gbp else 0 end)                                               as fees_and_other_gbp,
        sum(ft.value_gbp)                                                                    as net_cash_movement_gbp

    from {{ ref('fct_transactions') }} ft
    inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
    inner join {{ ref('dim_date') }}             dd  on dd.date_key              = ft.trade_date_key
    inner join {{ ref('dim_account') }}          da  on da.account_key           = ft.account_key

    group by dd.date_key, ft.account_key
)

select
    date_key,
    account_key,
    trade_cash_net_gbp,
    contributions_gbp,
    fees_and_other_gbp,
    net_cash_movement_gbp,
    sum(net_cash_movement_gbp) over (
        partition by account_key
        order by date_key
        rows between unbounded preceding and current row
    )                                                                                        as cash_balance_gbp

from daily_movements
