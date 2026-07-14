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


def _run(label: str, cmd: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    """Run a subprocess. Returns (success, stdout)."""
    logger.info("%s starting", label)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        logger.error("%s failed:\n%s", label, result.stderr)
        notify(
            f"❌ <b>HL Dashboard — {label} failed</b>\n\n<pre>{result.stderr[-1000:]}</pre>"
        )
        return False, ""
    logger.info("%s completed OK", label)
    return True, result.stdout


def _parse_inserted(stdout: str) -> int:
    """Extract the count from an 'INSERTED: N' summary line in a script's stdout."""
    for line in stdout.splitlines():
        if line.startswith("INSERTED:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
    return 0


def _fmt_date(d) -> str:
    return d.strftime("%b-%y") if d else "—"


def _pct_str(monthly_return: float | None) -> str:
    if monthly_return is None:
        return "new"
    sign = "+" if monthly_return >= 0 else ""
    return f"{sign}{monthly_return * 100:.1f}%"


def _monthly_summary() -> str:
    try:
        import duckdb

        con = duckdb.connect(str(_DB_PATH), read_only=True)

        # Joined against the snapshot (not just the returns mart) so that
        # accounts/funds with no prior month — e.g. a fund bought for the
        # first time this month — still show up, just without a % return.
        account_rows = con.execute("""
            SELECT s.account_name, s.month_end_date, s.month_end_value_gbp,
                   r.prev_month_end_value_gbp, s.monthly_inflows_gbp, r.monthly_return
            FROM mart_portfolio_snapshot_monthly s
            LEFT JOIN mart_portfolio_returns_monthly r
                ON  r.account_name = s.account_name
                AND r.year_month   = s.year_month
            WHERE s.month_end_date = (SELECT MAX(month_end_date) FROM mart_portfolio_snapshot_monthly)
            ORDER BY s.account_name
        """).fetchall()

        fund_rows = con.execute("""
            SELECT s.account_name, s.fund_name, s.fund_short_name, s.month_end_value_gbp, r.monthly_return
            FROM mart_fund_snapshot_monthly s
            LEFT JOIN mart_fund_returns_monthly r
                ON  r.account_name = s.account_name
                AND r.fund_name    = s.fund_name
                AND r.year_month   = s.year_month
            WHERE s.month_end_date = (SELECT MAX(month_end_date) FROM mart_fund_snapshot_monthly)
            ORDER BY s.account_name, s.fund_name
        """).fetchall()

        con.close()

        if not account_rows:
            return ""

        month_end_date = account_rows[0][1]
        total_value = sum(r[2] for r in account_rows)
        total_bmv = sum(r[3] for r in account_rows if r[3] is not None) or None
        total_inflows = sum(r[4] for r in account_rows)
        total_return = (
            (total_value - total_bmv - total_inflows) / (total_bmv + 0.5 * total_inflows)
            if total_bmv and (total_bmv + 0.5 * total_inflows) != 0
            else None
        )

        lines = [
            f"📊 <b>Monthly portfolio summary ({_fmt_date(month_end_date)})</b>",
            "",
            f"Total:   <b>£{total_value:,.0f}</b>  ({_pct_str(total_return)})",
            f"Inflows: £{total_inflows:,.0f}",
            "",
        ]
        for account_name, _, value, _, _, monthly_return in account_rows:
            lines.append(f"{account_name}: £{value:,.0f}  ({_pct_str(monthly_return)})")
            for fa_name, fund_name, fund_short_name, fund_value, fund_return in fund_rows:
                if fa_name != account_name:
                    continue
                label = fund_short_name or fund_name
                lines.append(f"    {label}: £{fund_value:,.0f}  ({_pct_str(fund_return)})")

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
    ok, _ = _run(
        "download_transactions.py",
        [sys.executable, str(_SCRIPTS_DIR / "download_transactions.py")],
    )
    if not ok:
        return  # failure notification already sent


def daily_refresh() -> None:
    today = date.today()
    failures = []

    ok, tx_stdout = _run(
        "ingest_transactions.py",
        [sys.executable, str(_SCRIPTS_DIR / "ingest_transactions.py")],
    )
    if not ok:
        failures.append("ingest_transactions.py")

    ok, price_stdout = _run(
        "fetch_prices.py", [sys.executable, str(_SCRIPTS_DIR / "fetch_prices.py")]
    )
    if not ok:
        failures.append("fetch_prices.py")

    _dbt = str(Path(sys.executable).parent / "dbt")
    ok, _ = _run(
        "dbt build", [_dbt, "build", "--profiles-dir", "."], cwd=_DBT_PROJECT_DIR
    )
    if not ok:
        failures.append("dbt build")

    if failures:
        return  # failure notifications already sent per step

    # Success notification — silent (no banner/sound)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tx_rows = _parse_inserted(tx_stdout)
    price_rows = _parse_inserted(price_stdout)
    notify(
        f"✅ <b>HL Dashboard refresh complete</b> ({now})\n"
        f"Prices added: {price_rows:,}\n"
        f"Transactions added: {tx_rows:,}",
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
