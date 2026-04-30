import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import portfolio, funds, transactions

logger = logging.getLogger(__name__)

_FETCH_PRICES_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "fetch_prices.py"


def _run_fetch_prices() -> None:
    logger.info("Scheduled price fetch starting")
    result = subprocess.run(
        [sys.executable, str(_FETCH_PRICES_SCRIPT)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error("fetch_prices.py failed:\n%s", result.stderr)
    else:
        logger.info("fetch_prices.py completed OK")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_fetch_prices, "cron", hour=18, minute=0, id="daily_price_fetch")
    scheduler.start()
    logger.info("APScheduler started — daily price fetch scheduled at 18:00")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="HL Investment Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to specific origin in production
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(funds.router, prefix="/funds", tags=["funds"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])


@app.get("/health")
def health():
    return {"status": "ok"}
