{{ config(materialized='view') }}

select
    cast(month_end_date as date)                  as month_end_date,
    strftime(cast(month_end_date as date), '%Y-%m') as year_month,
    cast(value_gbp as double)                     as month_end_value_gbp,
    coalesce(cast(external_flow_gbp as double), 0) as external_flow_gbp

from {{ ref('pelm_monthly') }}
