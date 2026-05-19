select
    da.account_name,
    dd.financial_year,
    sum(ft.value_gbp) as contributions_gbp

from {{ ref('fct_transactions') }}           ft
inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
inner join {{ ref('dim_account') }}          da  on da.account_key           = ft.account_key
inner join {{ ref('dim_date') }}             dd  on dd.date_key              = ft.trade_date_key

where dtt.contribution_indicator = 'Contribution'

group by da.account_name, dd.financial_year
