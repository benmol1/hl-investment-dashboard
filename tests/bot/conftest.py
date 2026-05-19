import os

# Set required env vars before any bot module is imported during collection.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "123456")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
