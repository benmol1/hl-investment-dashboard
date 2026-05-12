import logging
import subprocess
import sys
import time
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_SCRIPTS_DIR = Path(__file__).parent / "scripts"
_DBT_PROJECT_DIR = Path(__file__).parent.parent / "dbt"


def _run(label: str, cmd: list[str], cwd: Path | None = None) -> None:
    logger.info("%s starting", label)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        logger.error("%s failed:\n%s", label, result.stderr)
    else:
        logger.info("%s completed OK", label)


def daily_refresh() -> None:
    _run("ingest_transactions.py", [sys.executable, str(_SCRIPTS_DIR / "ingest_transactions.py")])
    _run("fetch_prices.py", [sys.executable, str(_SCRIPTS_DIR / "fetch_prices.py")])
    _run("dbt build", ["dbt", "build", "--profiles-dir", "."], cwd=_DBT_PROJECT_DIR)


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(daily_refresh, "cron", hour=18, minute=0, id="daily_refresh")
    logger.info("Cron scheduler started — daily refresh at 18:00")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
