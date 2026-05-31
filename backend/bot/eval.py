"""
Bot evaluation harness — A/B test between bot versions.

Usage:
    uv run python -m backend.bot.eval

Requires ANTHROPIC_API_KEY in environment or a .env file at the repo root.
Results are saved to backend/bot/eval_results.json.

To compare two branches:
    git checkout main && uv run python -m backend.bot.eval
    cp backend/bot/eval_results.json eval_results_main.json
    git checkout claude/backend-rest-api-check-RYSua && uv run python -m backend.bot.eval
    cp backend/bot/eval_results.json eval_results_phase12.json
"""

import asyncio
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap: load .env and set dummy Telegram vars before importing bot modules
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    env_path = Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_dotenv()
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "eval-mode")
os.environ.setdefault("TELEGRAM_CHAT_ID", "0")

import duckdb
import anthropic as _anthropic

from backend.bot.claude import run_claude_loop
from backend.bot.config import CLAUDE_MODEL, DB_PATH

RESULTS_PATH = Path(__file__).parent / "eval_results.json"


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    id: str
    question: str
    difficulty: str  # simple | medium | complex
    ground_truth_sql: str
    ground_truth_description: str  # used in the judge prompt


TEST_CASES: list[TestCase] = [
    TestCase(
        id="Q01",
        question="What is my total portfolio value right now?",
        difficulty="simple",
        # TODO: confirm this covers all your holdings correctly.
        # mart_holdings_latest includes fund positions only (no cash row).
        # If you want to include cash balances too, join to fct_cash_position_daily
        # or check whether your mart already rolls up cash.
        ground_truth_sql="""
            SELECT ROUND(SUM(value_gbp), 0) AS total_value_gbp
            FROM mart_holdings_latest
        """,
        ground_truth_description="Total portfolio market value in GBP across all accounts",
    ),
    TestCase(
        id="Q02",
        question="What are my current ISA holdings and what percentage of the ISA does each fund represent?",
        difficulty="simple",
        # TODO: confirm 'ISA' is the exact account_name value in your data
        # (check: SELECT DISTINCT account_name FROM mart_holdings_latest)
        ground_truth_sql="""
            SELECT fund_name, ROUND(weight_pct, 1) AS weight_pct
            FROM mart_holdings_latest
            WHERE account_name = 'ISA'
            ORDER BY value_gbp DESC
        """,
        ground_truth_description="ISA fund names and their weight_pct, ordered by value descending",
    ),
    TestCase(
        id="Q03",
        question="How much have I contributed to my SIPP this financial year?",
        difficulty="simple",
        # TODO: this picks the most recent row by financial_year label (e.g. '2025/26').
        # Check that the label ordering works correctly for your data:
        #   SELECT DISTINCT financial_year FROM mart_contributions_by_financial_year ORDER BY 1
        ground_truth_sql="""
            SELECT contributions_gbp
            FROM mart_contributions_by_financial_year
            WHERE account_name = 'SIPP'
            ORDER BY financial_year DESC
            LIMIT 1
        """,
        ground_truth_description="SIPP new-money contributions in the most recent financial year (GBP)",
    ),
    TestCase(
        id="Q04",
        question="What was my total portfolio worth a year ago, and how much has it changed since then?",
        difficulty="medium",
        # TODO: DuckDB supports INTERVAL syntax; verify your valuation_date column is
        # a DATE type so the arithmetic works. If it's a string, cast it:
        #   CAST(valuation_date AS DATE) <= ...
        # Also confirm whether you want ISA+SIPP combined or just one account.
        ground_truth_sql="""
            WITH latest AS (
                SELECT MAX(valuation_date) AS d FROM mart_portfolio_value_daily
            ),
            current_val AS (
                SELECT SUM(portfolio_value_gbp) AS v
                FROM mart_portfolio_value_daily
                WHERE valuation_date = (SELECT d FROM latest)
            ),
            year_ago_val AS (
                SELECT SUM(portfolio_value_gbp) AS v
                FROM mart_portfolio_value_daily
                WHERE valuation_date = (
                    SELECT MAX(valuation_date) FROM mart_portfolio_value_daily
                    WHERE valuation_date <= (SELECT d - INTERVAL '1 year' FROM latest)
                )
            )
            SELECT
                ROUND(current_val.v, 0)                  AS current_value_gbp,
                ROUND(year_ago_val.v, 0)                 AS year_ago_value_gbp,
                ROUND(current_val.v - year_ago_val.v, 0) AS change_gbp
            FROM current_val, year_ago_val
        """,
        ground_truth_description="Total portfolio value now, ~1 year ago, and the GBP change",
    ),
    TestCase(
        id="Q05",
        question="Which of my current holdings has the highest unrealised gain percentage?",
        difficulty="medium",
        # TODO: this looks across all accounts combined; add 'AND account_name = ...'
        # if you want per-account. Also verify cost_basis_gbp > 0 correctly excludes
        # positions where cost basis is zero (fully switched-in with no buy cost recorded).
        ground_truth_sql="""
            SELECT fund_name, account_name,
                   ROUND(unrealised_gain_pct, 1) AS gain_pct,
                   ROUND(unrealised_gain_gbp, 0) AS gain_gbp
            FROM mart_holdings_latest
            WHERE cost_basis_gbp > 0
            ORDER BY unrealised_gain_pct DESC
            LIMIT 1
        """,
        ground_truth_description="Fund with the highest unrealised gain %, its name, account, gain %, and gain £",
    ),
    TestCase(
        id="Q06",
        question="How much of my portfolio's current value is down to investment growth versus money I've actually paid in?",
        difficulty="medium",
        # TODO: this sums across both ISA and SIPP on the latest date.
        # mart_portfolio_inflows_daily includes cumulative_inflows_gbp (contributions + transfers).
        # Verify that 'transfers' should be counted as money you 'paid in' for your purposes —
        # if not, you may want mart_contributions_by_financial_year instead.
        ground_truth_sql="""
            SELECT
                ROUND(SUM(portfolio_value_gbp), 0)    AS total_value_gbp,
                ROUND(SUM(cumulative_inflows_gbp), 0) AS total_invested_gbp,
                ROUND(SUM(portfolio_value_gbp) - SUM(cumulative_inflows_gbp), 0) AS growth_gbp
            FROM mart_portfolio_inflows_daily
            WHERE valuation_date = (SELECT MAX(valuation_date) FROM mart_portfolio_inflows_daily)
        """,
        ground_truth_description="Total value, cumulative inflows, and investment growth in GBP (both accounts combined)",
    ),
    TestCase(
        id="Q07",
        question="What has my portfolio returned over the last 12 months compared to the FTSE 100?",
        difficulty="complex",
        # TODO: this queries ISA only — change account_name if you want SIPP or both.
        # trailing_12m_return is a decimal (e.g. 0.123 = 12.3%); the query multiplies by 100.
        # Verify that the most recent year_month in both tables is the same period.
        ground_truth_sql="""
            SELECT
                ROUND(pr.trailing_12m_return * 100, 1) AS portfolio_12m_pct,
                ROUND(bm.trailing_12m_return * 100, 1) AS ftse100_12m_pct
            FROM mart_portfolio_returns_monthly pr
            CROSS JOIN mart_benchmarks_monthly bm
            WHERE pr.year_month = (SELECT MAX(year_month) FROM mart_portfolio_returns_monthly
                                   WHERE trailing_12m_return IS NOT NULL)
              AND bm.year_month = (SELECT MAX(year_month) FROM mart_benchmarks_monthly
                                   WHERE trailing_12m_return IS NOT NULL)
              AND bm.index_id   = 'FTSE100'
              AND pr.account_name = 'ISA'
        """,
        ground_truth_description="Trailing 12-month return for ISA portfolio vs FTSE 100, as percentage points",
    ),
    TestCase(
        id="Q08",
        question="Which financial year did I contribute the most new money across both accounts?",
        difficulty="complex",
        # TODO: SUM groups ISA + SIPP together. If you have other account_name values
        # in the table, they'll be included. Verify with:
        #   SELECT DISTINCT account_name FROM mart_contributions_by_financial_year
        ground_truth_sql="""
            SELECT financial_year,
                   ROUND(SUM(contributions_gbp), 0) AS total_contributions_gbp
            FROM mart_contributions_by_financial_year
            GROUP BY financial_year
            ORDER BY total_contributions_gbp DESC
            LIMIT 1
        """,
        ground_truth_description="Financial year with the highest combined ISA+SIPP contributions and the total amount",
    ),
    TestCase(
        id="Q09",
        question="What is my trailing 12-month Sharpe ratio, and how does it compare to the S&P 500 and NASDAQ?",
        difficulty="complex",
        # TODO: returns one row per account (ISA, SIPP separately).
        # trailing_12m_sharpe is null until 12 months of history exist — the subquery
        # filters to the most recent month where it is non-null.
        # Check whether you want ISA, SIPP, or both in the response.
        ground_truth_sql="""
            SELECT
                pr.account_name,
                ROUND(pr.trailing_12m_sharpe, 2) AS portfolio_sharpe,
                ROUND(MAX(CASE WHEN bm.index_id = 'SP500'   THEN bm.trailing_12m_sharpe END), 2) AS sp500_sharpe,
                ROUND(MAX(CASE WHEN bm.index_id = 'NASDAQ'  THEN bm.trailing_12m_sharpe END), 2) AS nasdaq_sharpe
            FROM mart_portfolio_returns_monthly pr
            CROSS JOIN mart_benchmarks_monthly bm
            WHERE pr.year_month = (
                SELECT MAX(year_month) FROM mart_portfolio_returns_monthly
                WHERE trailing_12m_sharpe IS NOT NULL
            )
            AND bm.year_month = (
                SELECT MAX(year_month) FROM mart_benchmarks_monthly
                WHERE trailing_12m_sharpe IS NOT NULL
            )
            GROUP BY pr.account_name, pr.trailing_12m_sharpe
            ORDER BY pr.account_name
        """,
        ground_truth_description="Trailing 12-month Sharpe ratio per account vs S&P 500 and NASDAQ",
    ),
    TestCase(
        id="Q10",
        question="How much did I pay in platform fees last year, and on which dates were they charged?",
        difficulty="complex",
        # TODO: 'last year' = previous calendar year (EXTRACT(year) - 1).
        # If you want the previous UK financial year instead, join to dim_date and
        # filter on financial_year label (e.g. '2024/25').
        # Also verify that transaction_type = 'FEE' captures all fee types —
        # run: SELECT DISTINCT transaction_type FROM dim_transaction_type
        ground_truth_sql="""
            SELECT
                da.account_name,
                dd.date                         AS fee_date,
                ROUND(ABS(ft.value_gbp), 2)     AS fee_gbp
            FROM fct_transactions ft
            JOIN dim_date             dd  ON dd.date_key              = ft.trade_date_key
            JOIN dim_account          da  ON da.account_key           = ft.account_key
            JOIN dim_transaction_type dtt ON dtt.transaction_type_key = ft.transaction_type_key
            WHERE dtt.transaction_type = 'FEE'
              AND EXTRACT(year FROM dd.date) = EXTRACT(year FROM current_date) - 1
            ORDER BY dd.date
        """,
        ground_truth_description="Fee transactions from the previous calendar year: account, date, and amount",
    ),
]


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

def run_ground_truth(sql: str) -> list[dict]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        rows = con.execute(sql.strip()).fetchall()
        cols = [d[0] for d in con.description]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Numeric accuracy scoring
# ---------------------------------------------------------------------------

def _extract_numbers(text: str) -> set[float]:
    """Pull all numeric values (plain, £-prefixed, or %-suffixed) from a string."""
    matches = re.findall(r"£?([\d,]+(?:\.\d+)?)\s*%?", text)
    result: set[float] = set()
    for m in matches:
        try:
            result.add(float(m.replace(",", "")))
        except ValueError:
            pass
    return result


def score_accuracy_numeric(ground_truth_rows: list[dict], response_text: str) -> float | None:
    """
    Fraction of non-zero ground-truth numeric values that appear in the bot response
    within tolerance (2% for values ≥ 100, 0.5% otherwise).
    Returns None if there are no numeric ground-truth values to check.
    """
    expected: list[float] = []
    for row in ground_truth_rows:
        for v in row.values():
            if v is None:
                continue
            try:
                f = float(v)
                if f != 0:
                    expected.append(f)
            except (TypeError, ValueError):
                pass

    if not expected:
        return None

    response_numbers = _extract_numbers(response_text)

    hits = 0
    for exp in expected:
        tol = 0.02 if abs(exp) >= 100 else 0.005
        if any(abs(r - exp) / max(abs(exp), 1e-9) <= tol for r in response_numbers):
            hits += 1

    return round(hits / len(expected), 2)


# ---------------------------------------------------------------------------
# Claude-as-judge
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """\
You are evaluating a response from a personal investment portfolio assistant bot.

Question asked by the user:
{question}

Ground truth from the database:
{ground_truth}

Bot response:
{response}

Score the response on TWO dimensions:

QUALITY (1–5): Is the response clear, concise, and genuinely useful?
  5 = perfect — accurate, well-phrased, right level of detail
  4 = good — minor phrasing or detail issue
  3 = adequate — answers the question but is verbose, unclear, or missing key context
  2 = poor — hard to follow, or partially correct at best
  1 = bad — unhelpful, confusing, or does not answer the question

ACCURACY (1–5): Do the figures and facts in the response match the ground truth?
  5 = all figures correct (rounding differences acceptable)
  4 = one minor figure off or rounded differently
  3 = some figures correct, some wrong or missing
  2 = mostly wrong or missing figures
  1 = no correct figures, or question not answered at all

Reply in EXACTLY this format (no extra text):
QUALITY: <1-5>
ACCURACY: <1-5>
REASONING: <one sentence explaining the scores>
"""


def judge_response(
    question: str, ground_truth_rows: list[dict], response_text: str
) -> dict[str, Any]:
    client = _anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = _JUDGE_PROMPT.format(
        question=question,
        ground_truth=json.dumps(ground_truth_rows, default=str, indent=2),
        response=response_text,
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    quality = accuracy_j = None
    reasoning = ""
    for line in text.splitlines():
        if line.startswith("QUALITY:"):
            try:
                quality = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("ACCURACY:"):
            try:
                accuracy_j = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()
    return {"quality": quality, "accuracy_judge": accuracy_j, "reasoning": reasoning}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    test_case_id: str
    question: str
    difficulty: str
    response_text: str
    tools_called: list[str]
    tool_call_count: int
    latency_s: float
    input_tokens: int
    output_tokens: int
    ground_truth_rows: list[dict]
    accuracy_numeric: float | None
    quality_score: int | None
    accuracy_judge_score: int | None
    judge_reasoning: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Run a single test case
# ---------------------------------------------------------------------------

async def run_one(tc: TestCase) -> EvalResult:
    # Ground truth
    ground_truth_rows: list[dict] = []
    error: str | None = None
    try:
        ground_truth_rows = run_ground_truth(tc.ground_truth_sql)
    except Exception as exc:
        error = f"Ground truth SQL failed: {exc}"

    # Bot call
    tools_called: list[str] = []

    async def _capture(round_tools: list[str]) -> None:
        tools_called.extend(round_tools)

    t0 = time.perf_counter()
    response_text = ""
    input_tokens = output_tokens = 0
    try:
        bot_resp = await run_claude_loop(tc.question, on_tool_call=_capture)
        response_text = bot_resp.text
        input_tokens = bot_resp.usage.get("input_tokens", 0)
        output_tokens = bot_resp.usage.get("output_tokens", 0)
    except Exception as exc:
        error = (error + " | " if error else "") + f"Bot call failed: {exc}"
    latency_s = round(time.perf_counter() - t0, 2)

    # Scoring
    accuracy_numeric: float | None = None
    quality_score = accuracy_judge_score = None
    judge_reasoning = ""

    if response_text and ground_truth_rows:
        accuracy_numeric = score_accuracy_numeric(ground_truth_rows, response_text)
        judge = await asyncio.to_thread(
            judge_response, tc.question, ground_truth_rows, response_text
        )
        quality_score = judge["quality"]
        accuracy_judge_score = judge["accuracy_judge"]
        judge_reasoning = judge["reasoning"]

    return EvalResult(
        test_case_id=tc.id,
        question=tc.question,
        difficulty=tc.difficulty,
        response_text=response_text,
        tools_called=list(dict.fromkeys(tools_called)),
        tool_call_count=len(tools_called),
        latency_s=latency_s,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        ground_truth_rows=ground_truth_rows,
        accuracy_numeric=accuracy_numeric,
        quality_score=quality_score,
        accuracy_judge_score=accuracy_judge_score,
        judge_reasoning=judge_reasoning,
        error=error,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _fmt(val: int | float | None, suffix: str = "") -> str:
    if val is None:
        return "  —"
    return f"{val}{suffix}"


async def main() -> None:
    print(f"\n{'─' * 84}")
    print(f"  HL bot eval  |  {date.today()}  |  model: {CLAUDE_MODEL}")
    print(f"{'─' * 84}\n")

    results: list[EvalResult] = []

    for tc in TEST_CASES:
        print(f"  [{tc.id}] {tc.difficulty:<8}  {tc.question[:60]}...")
        result = await run_one(tc)
        results.append(result)
        status = "✗" if result.error else "✓"
        print(
            f"          {status}  {result.latency_s:>5.1f}s  "
            f"tok={result.input_tokens}+{result.output_tokens}  "
            f"tools={result.tool_call_count}  "
            f"qual={_fmt(result.quality_score)}/5  "
            f"acc={_fmt(result.accuracy_judge_score)}/5"
        )
        if result.error:
            print(f"          ↳ {result.error}")
        if result.judge_reasoning:
            print(f"          ↳ {result.judge_reasoning}")

    # Summary table
    w = 84
    print(f"\n{'─' * w}")
    print(f"{'ID':<5} {'Diff':<9} {'Lat':>6} {'In tok':>7} {'Out tok':>8} {'Tools':>6} {'Qual':>5} {'Acc':>5}  Tool sequence")
    print(f"{'─' * w}")
    for r in results:
        print(
            f"{r.test_case_id:<5} {r.difficulty:<9} {r.latency_s:>5.1f}s "
            f"{r.input_tokens:>7} {r.output_tokens:>8} "
            f"{r.tool_call_count:>6}  "
            f"{_fmt(r.quality_score):>4}/5 "
            f"{_fmt(r.accuracy_judge_score):>4}/5  "
            f"{' → '.join(r.tools_called) or '—'}"
        )

    scored = [r for r in results if r.quality_score is not None]
    if scored:
        print(f"{'─' * w}")
        print(
            f"{'AVG':<5} {'':<9} "
            f"{sum(r.latency_s for r in results) / len(results):>5.1f}s "
            f"{sum(r.input_tokens for r in results) // len(results):>7} "
            f"{sum(r.output_tokens for r in results) // len(results):>8} "
            f"{sum(r.tool_call_count for r in results) / len(results):>6.1f}  "
            f"{sum(r.quality_score for r in scored) / len(scored):>4.1f}/5 "
            f"{sum(r.accuracy_judge_score for r in scored) / len(scored):>4.1f}/5"
        )

    # Save JSON
    out = [asdict(r) for r in results]
    RESULTS_PATH.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n  Results saved → {RESULTS_PATH}\n")
    print(f"{'─' * w}\n")


if __name__ == "__main__":
    asyncio.run(main())
