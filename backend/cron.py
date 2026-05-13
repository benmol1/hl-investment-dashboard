import logging
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_SCRIPTS_DIR = Path(__file__).parent / "scripts"
_DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt"
_DB_PATH = Path(__file__).parent.parent / "data" / "hl_dashboard.duckdb"

_TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
_TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def notify(message: str) -> None:
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT_ID:
        logger.warning("Telegram env vars not set — skipping notification")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Telegram notification failed: %s", exc)


def _run(label: str, cmd: list[str], cwd: Path | None = None) -> bool:
    logger.info("%s starting", label)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        logger.error("%s failed:\n%s", label, result.stderr)
        notify(f"❌ <b>HL Dashboard — {label} failed</b>\n\n<pre>{result.stderr[-1000:]}</pre>")
        return False
    logger.info("%s completed OK", label)
    return True


def _fmt_date(d) -> str:
    return d.strftime("%b-%y") if d else "—"


def _delta_str(value: float, prev: float | None) -> str:
    if not prev:
        return ""
    change = value - prev
    pct = change / prev * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}£{change:,.0f} / {sign}{pct:.1f}%"


def _monthly_summary() -> str:
    try:
        import duckdb
        con = duckdb.connect(str(_DB_PATH), read_only=True)
        rows = con.execute("""
            WITH ranked AS (
                SELECT account_name, month_end_date, month_end_value_gbp,
                       monthly_contributions_gbp,
                       LAG(month_end_value_gbp) OVER (PARTITION BY account_name ORDER BY month_end_date) AS prev_value
                FROM mart_monthly_snapshot
            )
            SELECT account_name, month_end_date, month_end_value_gbp, prev_value, monthly_contributions_gbp
            FROM ranked
            WHERE month_end_date = (SELECT MAX(month_end_date) FROM mart_monthly_snapshot)
            ORDER BY account_name
        """).fetchall()
        con.close()

        if not rows:
            return ""

        month_end_date = rows[0][1]
        total = sum(r[2] for r in rows)
        total_prev = sum(r[3] for r in rows if r[3] is not None) or None
        total_contributions = sum(r[4] for r in rows if r[4] is not None)

        lines = [
            f"📊 <b>Monthly portfolio summary ({_fmt_date(month_end_date)})</b>",
            "",
            f"Total:         <b>£{total:,.0f}</b>",
            f"Change:        {_delta_str(total, total_prev)}",
            f"Contributions: £{total_contributions:,.0f}",
            "",
        ]
        for account_name, _, value, prev, _ in rows:
            lines.append(f"{account_name}: £{value:,.0f}  ({_delta_str(value, prev)})")

        return "\n".join(lines)
    except Exception as exc:
        logger.warning("Monthly summary query failed: %s", exc)
        return ""


def daily_refresh() -> None:
    today = date.today()
    failures = []

    if not _run("ingest_transactions.py", [sys.executable, str(_SCRIPTS_DIR / "ingest_transactions.py")]):
        failures.append("ingest_transactions.py")

    if not _run("fetch_prices.py", [sys.executable, str(_SCRIPTS_DIR / "fetch_prices.py")]):
        failures.append("fetch_prices.py")

    if not _run("dbt build", ["dbt", "build", "--profiles-dir", "."], cwd=_DBT_PROJECT_DIR):
        failures.append("dbt build")

    if failures:
        return  # failure notifications already sent per step

    # Daily success notification
    notify(f"✅ <b>HL Dashboard refresh complete</b> ({today})\nAll steps passed.")

    # Monthly summary on the first of the month
    if today.day == 1:
        summary = _monthly_summary()
        if summary:
            notify(summary)


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(daily_refresh, "cron", hour=18, minute=0, id="daily_refresh")
    logger.info("Cron scheduler started — daily refresh at 18:00")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
