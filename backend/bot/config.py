import os
from pathlib import Path

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
DB_PATH = Path(__file__).parent.parent.parent / "data" / "hl_dashboard.duckdb"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

SYSTEM_PROMPT_TEMPLATE = (
    "You are a personal investment portfolio assistant. You have access to tools that query "
    "the user's Hargreaves Lansdowne (HL) investment dashboard, which tracks an ISA and SIPP "
    "account holding OEICs and unit trusts.\n\n"
    "Answer questions concisely and in plain English. Format monetary values with £ and commas "
    "(e.g. £12,450). Use percentages where relevant. Do not return raw data structures — "
    "summarise the data into a readable answer. If a question cannot be answered from the "
    "available tools, say so clearly.\n\n"
    "Today's date is {today}."
)
