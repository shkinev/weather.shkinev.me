from __future__ import annotations

import asyncio

from loguru import logger
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import TELEGRAM_BOT_TOKEN
from app.db import format_telegram_snapshot, get_latest_snapshot, init_db
from app.logging_setup import setup_logging


WEATHER_BUTTON = "Погода сейчас"


def keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(WEATHER_BUTTON)]],
        resize_keyboard=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    logger.info("Telegram /start user_id={} chat_id={}", update.effective_user.id if update.effective_user else "?", update.effective_chat.id if update.effective_chat else "?")
    await update.message.reply_text(
        "Нажмите кнопку, чтобы получить актуальную сводку погоды.",
        reply_markup=keyboard(),
    )


async def send_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    text = (update.message.text or "").strip()
    logger.info(
        "Telegram request user_id={} chat_id={} text={!r}",
        update.effective_user.id if update.effective_user else "?",
        update.effective_chat.id if update.effective_chat else "?",
        text,
    )
    try:
        await update.message.reply_text(format_telegram_snapshot(get_latest_snapshot()), reply_markup=keyboard())
    except Exception:
        logger.exception("Failed to send weather message to chat_id={}", update.effective_chat.id if update.effective_chat else "?")
        await update.message.reply_text(
            "Не удалось получить данные погоды. Проверьте логи и подключение к базе.",
            reply_markup=keyboard(),
        )


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    incoming = (update.message.text or "").strip().lower()
    if incoming in {WEATHER_BUTTON.lower(), "погода", "погода сейчас", "/weather"}:
        await send_weather(update, context)
        return
    await update.message.reply_text(
        "Используйте кнопку «Погода сейчас» или команду /weather.",
        reply_markup=keyboard(),
    )


def build_app() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN before starting the bot.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("weather", send_weather))
    app.add_handler(MessageHandler(filters.Regex(f"^{WEATHER_BUTTON}$"), send_weather))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


async def main() -> None:
    setup_logging("bot")
    init_db()
    logger.info("Bot service started")
    application = build_app()
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    try:
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
