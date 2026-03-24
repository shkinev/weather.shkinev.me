from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import (
    TELEGRAM_ADMIN_IDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_DAILY_TIMES,
    TELEGRAM_DAILY_USER_IDS,
    TELEGRAM_DYNAMIC_NAME_ENABLED,
    TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES,
    TELEGRAM_DYNAMIC_NAME_PREFIX,
    TELEGRAM_MONITOR_INTERVAL_SECONDS,
    TELEGRAM_STALE_MINUTES,
    WEATHER_TIMEZONE,
)
from app.db import format_telegram_snapshot, get_latest_snapshot, init_db, parse_timestamp
from app.logging_setup import setup_logging

try:
    APP_TZ = ZoneInfo(WEATHER_TIMEZONE)
except ZoneInfoNotFoundError:
    APP_TZ = UTC

WEATHER_BUTTON = "Погода сейчас"


def keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(WEATHER_BUTTON)]],
        resize_keyboard=True,
    )


def current_weather_text() -> str:
    return format_telegram_snapshot(get_latest_snapshot())


def build_dynamic_bot_name(snapshot: dict | None) -> str:
    suffix = "нет данных"
    if snapshot:
        for reading in snapshot.get("readings", []):
            if str(reading.get("sensor_id", "")).upper() == "T1":
                try:
                    suffix = f"{float(reading['value']):.2f} С"
                except (TypeError, ValueError, KeyError):
                    suffix = "нет данных"
                break
    title = f"{TELEGRAM_DYNAMIC_NAME_PREFIX} - {suffix}"
    if len(title) > 64:
        title = title[:64].rstrip()
    return title


async def send_text_to_chat(app: Application, chat_id: int, text: str) -> None:
    try:
        await app.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard())
    except Exception:
        logger.exception("Failed to send telegram message to chat_id={}", chat_id)


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
        await update.message.reply_text(current_weather_text(), reply_markup=keyboard())
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


async def stale_data_monitor_loop(app: Application) -> None:
    logger.info(
        "Stale monitor started: stale_minutes={} interval_sec={} admin_ids={}",
        TELEGRAM_STALE_MINUTES,
        TELEGRAM_MONITOR_INTERVAL_SECONDS,
        TELEGRAM_ADMIN_IDS,
    )
    notified = False
    while True:
        snapshot = get_latest_snapshot()
        stale_minutes = None
        if snapshot and snapshot.get("received_at"):
            observed_at = parse_timestamp(snapshot["received_at"])
            stale_minutes = (datetime.now(UTC) - observed_at).total_seconds() / 60.0

        is_stale = snapshot is None or stale_minutes is None or stale_minutes >= TELEGRAM_STALE_MINUTES
        if is_stale and not notified and TELEGRAM_ADMIN_IDS:
            if snapshot and stale_minutes is not None:
                text = (
                    "⚠️ Нет новых данных от станции.\n"
                    f"Последнее обновление: {snapshot.get('received_ago', 'давно')}.\n"
                    f"Порог: {TELEGRAM_STALE_MINUTES} мин."
                )
            else:
                text = (
                    "⚠️ Нет данных от станции.\n"
                    "В базе нет актуальных пакетов телеметрии."
                )
            logger.warning("Station data stale. Sending alert to admins.")
            for admin_id in TELEGRAM_ADMIN_IDS:
                await send_text_to_chat(app, admin_id, text)
            notified = True

        if not is_stale and notified:
            logger.info("Station data flow restored")
            notified = False

        await asyncio.sleep(max(15, TELEGRAM_MONITOR_INTERVAL_SECONDS))


async def daily_weather_broadcast_loop(app: Application) -> None:
    logger.info(
        "Daily weather broadcast started: times={} user_ids={}",
        TELEGRAM_DAILY_TIMES,
        TELEGRAM_DAILY_USER_IDS,
    )
    sent_keys: set[str] = set()
    while True:
        now_local = datetime.now(APP_TZ)
        hhmm = now_local.strftime("%H:%M")
        for schedule in TELEGRAM_DAILY_TIMES:
            key = f"{now_local.date().isoformat()}-{schedule}"
            if hhmm == schedule and key not in sent_keys and TELEGRAM_DAILY_USER_IDS:
                payload = current_weather_text()
                logger.info("Daily broadcast at {} for {} users", schedule, len(TELEGRAM_DAILY_USER_IDS))
                for user_id in TELEGRAM_DAILY_USER_IDS:
                    await send_text_to_chat(app, user_id, payload)
                sent_keys.add(key)

        # keep only today's keys
        today_prefix = f"{now_local.date().isoformat()}-"
        sent_keys = {key for key in sent_keys if key.startswith(today_prefix)}
        await asyncio.sleep(20)


async def dynamic_bot_name_loop(app: Application) -> None:
    if not TELEGRAM_DYNAMIC_NAME_ENABLED:
        logger.info("Dynamic bot name disabled")
        return

    interval_minutes = max(1, TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES)
    logger.info(
        "Dynamic bot name started: every {} min, prefix={!r}",
        interval_minutes,
        TELEGRAM_DYNAMIC_NAME_PREFIX,
    )
    last_name = ""
    while True:
        try:
            snapshot = get_latest_snapshot()
            new_name = build_dynamic_bot_name(snapshot)
            if new_name != last_name:
                await app.bot.set_my_name(name=new_name)
                logger.info("Bot name updated: {}", new_name)
                last_name = new_name
        except Exception:
            logger.exception("Failed to update bot name")
        await asyncio.sleep(interval_minutes * 60)


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

    monitor_task = asyncio.create_task(stale_data_monitor_loop(application))
    broadcast_task = asyncio.create_task(daily_weather_broadcast_loop(application))
    dynamic_name_task = asyncio.create_task(dynamic_bot_name_loop(application))
    try:
        await asyncio.Event().wait()
    finally:
        monitor_task.cancel()
        broadcast_task.cancel()
        dynamic_name_task.cancel()
        await asyncio.gather(monitor_task, broadcast_task, dynamic_name_task, return_exceptions=True)
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
