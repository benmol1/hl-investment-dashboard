# Eval Comparison: master vs claude/backend-rest-api-check-RYSua

**Date:** 2026-06-04  
**master file:** `master_2da3861_20260604_1410.json`  
**experimental file:** `claude-backend-rest-api-check-RYSua_9b45cb2_20260604_1508.json`

---

## Aggregate Summary

| Metric | master | experimental | Delta |
|---|---|---|---|
| **Avg latency** | 9.94s | 17.25s | +73% slower |
| **Avg input tokens** | 7,624 | 12,462 | +63% more |
| **Avg output tokens** | 220 | 565 | +157% more |
| **Avg quality score** | 4.7 / 5 | 4.0 / 5 | −0.7 |
| **Avg accuracy (judge)** | 3.6 / 5 | 3.4 / 5 | −0.2 |
| **Avg accuracy (numeric)** | 0.871 | 0.854 | −0.017 |

---

## Per-question Breakdown

| Q | Difficulty | master latency | exp latency | master quality | exp quality | master acc (judge) | exp acc (judge) |
|---|---|---|---|---|---|---|---|
| Q01 | simple | 11.1s | 7.2s | 5 | 5 | 4 | 5 ⬆ |
| Q02 | simple | 8.4s | 9.7s | 5 | 4 | 4 | 2 ⬇ |
| Q03 | simple | 6.7s | 10.4s | 5 | 5 | 5 | 5 |
| Q04 | medium | 11.4s | 8.8s | 4 | 4 | 2 | 2 |
| Q05 | medium | 10.6s | 7.2s | 5 | 4 | 4 | 1 ⬇ |
| Q06 | medium | 7.7s | 11.9s | 5 | 2 ⬇ | 5 | 2 ⬇ |
| Q07 | complex | 7.9s | 43.1s ⬆ | 4 | 2 ⬇ | 2 | 2 |
| Q08 | medium | 7.4s | 17.9s | 5 | 5 | 4 | 5 ⬆ |
| Q09 | complex | 13.9s | 20.4s | 4 | 4 | 2 | 5 ⬆ |
| Q10 | complex | 14.4s | 36.0s | 5 | 5 | 4 | 5 ⬆ |

---

## Key Observations

### Latency / Token Usage — master wins clearly

The experimental branch replaces purpose-built API tools (`get_holdings`, `get_portfolio_performance`, etc.) with `get_model_schema` + `query_database`. This is far more expensive: it fetches schemas first, then constructs SQL, leading to 2–7 tool calls where master uses 1. Q07 is the worst case at 43s / 24k input tokens (7 tool calls including `generate_chart`), vs 7.9s / 6.9k on master. Q03 jumped from 1 tool call to 4. Q10 went from 2 calls to 5, with latency roughly doubling.

### Accuracy — mixed, with a concerning fabrication pattern

The experimental branch scores better on some harder questions (Q08: +1, Q09: +3, Q10: +1) — particularly where it benefits from querying raw data directly rather than relying on a pre-built endpoint that may aggregate imprecisely. However, there is a clear failure mode: when the SQL returns data that does not directly answer the question, the experimental branch invents plausible-sounding breakdowns:

- **Q06:** Fabricated per-account ISA/SIPP growth splits not present in ground truth — quality dropped 5→2
- **Q07:** Fabricated specific monthly return commentary ("Feb 2026 pullback", "March sell-off of −5.7%") — quality dropped 4→2
- **Q05:** Gain % was wildly wrong (66% vs 43.6% ground truth) — accuracy_judge 4→1, accuracy_numeric 0.5→0.0

### Quality — master wins

Master avg 4.7 vs 4.0. The experimental branch's verbose responses sometimes pad with unverifiable detail rather than answering precisely.

### Q09 — standout win for experimental

Master scored accuracy_judge=2 on Q09 because it included FTSE 100 (1.42) as a spurious benchmark not in the ground truth. Experimental correctly restricted its table to only the data it queried, earning a 5. This suggests that when the experimental branch does not over-reach, the `query_database` path is actually more faithful to the data.

---

## Bottom Line

The experimental branch's flexible SQL approach pays off for complex multi-part queries (Q09, Q10) but at significant latency and token cost, and introduces a hallucination risk when it cannot find an exact answer in the query results. Master is faster, cheaper, and more consistent — the main gap is Q09's benchmark contamination issue.

The experimental branch's fabrication failures (Q05, Q06, Q07) are the most concerning finding: the model over-extends into made-up detail rather than stopping at what the data actually supports.
