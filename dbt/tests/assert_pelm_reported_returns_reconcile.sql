-- Fails if the dashboard's PELM return for a fully covered report period differs from Barratt &
-- Cooke's reported figure by more than 0.1 percentage points. Linking monthly Modified Dietz
-- returns instead of daily ones accounts for a few hundredths of a point; more than 0.1pp means a
-- missing or misclassified cash flow, or a mistyped valuation or reported return.
select
    period_start,
    period_end,
    reported_return,
    dashboard_return,
    difference_pp
from {{ ref('mart_pelm_return_reconciliation') }}
where cash_flow_coverage_indicator = 'Complete'
  and abs(difference_pp) > 0.1
