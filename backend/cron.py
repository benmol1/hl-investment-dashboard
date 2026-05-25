import logging
import os
import subprocess
import sys
from datetime import date, datetime
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


def notify(message: str, silent: bool = False) -> None:
    if not _TELEGRAM_TOKEN or not _TELEGRAM_CHAT_ID:
        logger.warning("Telegram env vars not set — skipping notification")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{_TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": _TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_notification": silent,
            },
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Telegram notification failed: %s", exc)


def _run(label: str, cmd: list[str], cwd: Path | None = None) -> bool:
    logger.info("%s starting", label)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        logger.error("%s failed:\n%s", label, result.stderr)
        notify(
            f"❌ <b>HL Dashboard — {label} failed</b>\n\n<pre>{result.stderr[-1000:]}</pre>"
        )
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


def _get_refresh_stats() -> tuple[int, int]:
    """
    Read the rows_inserted counts from the most recent successful ingest_log
    entries for 'prices' and 'transactions'. Returns (price_rows, tx_rows).
    """
    try:
        import duckdb

        con = duckdb.connect(str(_DB_PATH), read_only=True)
        price_row = con.execute("""
            SELECT rows_inserted FROM ingest_log
            WHERE source = 'prices' AND status = 'success'
            ORDER BY run_at DESC LIMIT 1
        """).fetchone()
        tx_row = con.execute("""
            SELECT rows_inserted FROM ingest_log
            WHERE source = 'transactions' AND status = 'success'
            ORDER BY run_at DESC LIMIT 1
        """).fetchone()
        con.close()
        return (
            price_row[0] if price_row else 0,
            tx_row[0] if tx_row else 0,
        )
    except Exception as exc:
        logger.warning("Could not read refresh stats from ingest_log: %s", exc)
        return 0, 0


def _monthly_summary() -> str:
    try:
        import duckdb

        con = duckdb.connect(str(_DB_PATH), read_only=True)
        rows = con.execute("""
            WITH ranked AS (
                SELECT account_name, month_end_date, month_end_value_gbp,
                       monthly_inflows_gbp,
                       LAG(month_end_value_gbp) OVER (PARTITION BY account_name ORDER BY month_end_date) AS prev_value
                FROM mart_portfolio_snapshot_monthly
            )
            SELECT account_name, month_end_date, month_end_value_gbp, prev_value, monthly_inflows_gbp
            FROM ranked
            WHERE month_end_date = (SELECT MAX(month_end_date) FROM mart_portfolio_snapshot_monthly)
            ORDER BY account_name
        """).fetchall()
        con.close()

        if not rows:
            return ""

        month_end_date = rows[0][1]
        total = sum(r[2] for r in rows)
        total_prev = sum(r[3] for r in rows if r[3] is not None) or None
        total_inflows = sum(r[4] for r in rows if r[4] is not None)

        lines = [
            f"📊 <b>Monthly portfolio summary ({_fmt_date(month_end_date)})</b>",
            "",
            f"Total:         <b>£{total:,.0f}</b>",
            f"Change:        {_delta_str(total, total_prev)}",
            f"Inflows:       £{total_inflows:,.0f}",
            "",
        ]
        for account_name, _, value, prev, _ in rows:
            lines.append(f"{account_name}: £{value:,.0f}  ({_delta_str(value, prev)})")

        return "\n".join(lines)
    except Exception as exc:
        logger.warning("Monthly summary query failed: %s", exc)
        return ""


def weekly_download() -> None:
    # Download fresh CSVs from HL. Runs weekly (Sunday 00:00) so the daily
    # refresh at 01:00 picks up the new files on Sunday morning.
    # Skipped silently if HL_USERNAME is not configured.
    if not os.environ.get("HL_USERNAME"):
        return
    if not _run(
        "download_transactions.py",
        [sys.executable, str(_SCRIPTS_DIR / "download_transactions.py")],
    ):
        return  # failure notification already sent


def daily_refresh() -> None:
    today = date.today()
    failures = []

    if not _run(
        "ingest_transactions.py",
        [sys.executable, str(_SCRIPTS_DIR / "ingest_transactions.py")],
    ):
        failures.append("ingest_transactions.py")

    if not _run(
        "fetch_prices.py", [sys.executable, str(_SCRIPTS_DIR / "fetch_prices.py")]
    ):
        failures.append("fetch_prices.py")

    _dbt = str(Path(sys.executable).parent / "dbt")
    if not _run(
        "dbt build", [_dbt, "build", "--profiles-dir", "."], cwd=_DBT_PROJECT_DIR
    ):
        failures.append("dbt build")

    if failures:
        return  # failure notifications already sent per step

    # Success notification — silent (no banner/sound)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    price_rows, tx_rows = _get_refresh_stats()
    notify(
        f"✅ <b>HL Dashboard refresh complete</b> ({now})\n"
        f"Prices added: {price_rows:,}  |  Transactions added: {tx_rows:,}",
        silent=True,
    )

    # Monthly summary on the first of the month
    if today.day == 1:
        summary = _monthly_summary()
        if summary:
            notify(summary)


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(daily_refresh, "cron", hour=1, minute=0, id="daily_refresh")
    scheduler.add_job(
        weekly_download,
        "cron",
        day_of_week="sun",
        hour=0,
        minute=0,
        id="weekly_download",
    )
    logger.info(
        "Cron scheduler started — daily refresh at 01:00, HL download Sundays at 00:00"
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
