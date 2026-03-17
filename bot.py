from __future__ import annotations

import asyncio

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import TELEGRAM_BOT_TOKEN
from app.db import format_telegram_snapshot, get_latest_snapshot, init_db


WEATHER_BUTTON = "Погода сейчас"


def keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(WEATHER_BUTTON)]],
        resize_keyboard=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Нажмите кнопку, чтобы получить актуальную сводку погоды.",
        reply_markup=keyboard(),
    )


async def send_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(format_telegram_snapshot(get_latest_snapshot()), reply_markup=keyboard())


def build_app() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN before starting the bot.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(f"^{WEATHER_BUTTON}$"), send_weather))
    return app


async def main() -> None:
    init_db()
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
