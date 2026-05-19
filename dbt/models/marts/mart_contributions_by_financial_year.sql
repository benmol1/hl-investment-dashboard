select
    da.account_name,
    dd.financial_year,
    sum(case when dtt.contribution_indicator = 'Contribution' then ft.value_gbp else 0 end) as contributions_gbp,
    sum(case when dtt.contribution_indicator = 'Transfer'     then ft.value_gbp else 0 end) as transfers_gbp

from {{ ref('fct_transactions') }}           ft
inner join {{ ref('dim_transaction_type') }} dtt on dtt.transaction_type_key = ft.transaction_type_key
inner join {{ ref('dim_account') }}          da  on da.account_key           = ft.account_key
inner join {{ ref('dim_date') }}             dd  on dd.date_key              = ft.trade_date_key

where dtt.contribution_indicator in ('Contribution', 'Transfer')

group by da.account_name, dd.financial_year
