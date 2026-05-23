import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import portfolio, funds, transactions
from app.routers import auth as auth_routes

logger = logging.getLogger(__name__)

app = FastAPI(title="HL Investment Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to specific origin in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(funds.router, prefix="/funds", tags=["funds"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])


@app.get("/health")
def health():
    return {"status": "ok"}
