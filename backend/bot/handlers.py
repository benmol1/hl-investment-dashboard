import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from .claude import run_claude_loop
from .config import ALLOWED_CHAT_ID, TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _is_authorised(update: Update) -> bool:
    return update.effective_chat is not None and update.effective_chat.id == ALLOWED_CHAT_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorised(update):
        return
    await update.message.reply_text(
        "Hi! Ask me anything about your portfolio — e.g. \"what are my current holdings?\" "
        "or \"how has my ISA performed this year?\""
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorised(update):
        logger.warning(
            "Rejected message from chat_id=%s",
            update.effective_chat.id if update.effective_chat else "unknown",
        )
        return

    user_text = update.message.text
    logger.info("Received message: %s", user_text)

    thinking = await update.message.reply_text("Thinking…")
    try:
        answer = await run_claude_loop(user_text)
    except Exception as exc:
        logger.exception("Claude loop failed")
        answer = f"Sorry, something went wrong: {exc}"
    await thinking.edit_text(answer, parse_mode="Markdown")


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started — polling for messages")
    app.run_polling()
