# Weather Station Dashboard

Приложение для приема телеметрии от метеостанции, хранения данных в SQLite, просмотра текущей погоды, графиков и истории, плюс Telegram-бот.

## Что внутри

- `web`: FastAPI + Jinja2
- `bot`: Telegram-бот (polling)
- `data/weather.sqlite3`: база с телеметрией

Nginx работает на хосте отдельно, в контейнер не включен.

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

- `WEATHER_DB_PATH=/data/weather.sqlite3`
- `TELEGRAM_BOT_TOKEN=...`
- `WEB_BIND_PORT=18080`
- `WEATHER_TIMEZONE=Asia/Omsk`
- `LOG_DIR=/logs`
- `WEATHER_SITE_URL=https://weather.shkinev.me`
- `TELEGRAM_ADMIN_IDS=123456789,987654321`
- `TELEGRAM_DAILY_USER_IDS=123456789,987654321`
- `TELEGRAM_DAILY_TIMES=07:00,20:00`
- `TELEGRAM_STALE_MINUTES=5`
- `TELEGRAM_MONITOR_INTERVAL_SECONDS=60`
- `TELEGRAM_DYNAMIC_NAME_ENABLED=1`
- `TELEGRAM_DYNAMIC_NAME_PREFIX=Погода в КП "Аист"`
- `TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES=10`

## Запуск в Docker

```bash
docker compose up -d --build
```

Логи будут на хосте в папке `./logs`:

- `logs/web.log`
- `logs/bot.log`

Остановить:

```bash
docker compose down
```

Веб будет доступен на:

- `http://127.0.0.1:18080`

## Локальный запуск без Docker (Windows, PowerShell)

1. Создать и активировать виртуальное окружение:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Установить зависимости:

```powershell
pip install -r requirements.txt
```

3. Указать путь к базе и таймзону:

```powershell
$env:WEATHER_DB_PATH="data/weather.sqlite3"
$env:WEATHER_TIMEZONE="Asia/Omsk"
$env:LOG_DIR="logs"
```

4. Запустить веб:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

5. Открыть:

- `http://127.0.0.1:8000`

6. (Опционально) запустить бота во второй консоли:

```powershell
$env:WEATHER_DB_PATH="data/weather.sqlite3"
$env:WEATHER_TIMEZONE="Asia/Omsk"
$env:LOG_DIR="logs"
$env:TELEGRAM_BOT_TOKEN="ваш_токен"
$env:TELEGRAM_ADMIN_IDS="123456789"
$env:TELEGRAM_DAILY_USER_IDS="123456789,987654321"
$env:TELEGRAM_DAILY_TIMES="07:00,20:00"
$env:TELEGRAM_STALE_MINUTES="5"
$env:TELEGRAM_MONITOR_INTERVAL_SECONDS="60"
$env:TELEGRAM_DYNAMIC_NAME_ENABLED="1"
$env:TELEGRAM_DYNAMIC_NAME_PREFIX='Погода в КП "Аист"'
$env:TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES="10"
py -3 bot.py
```

## API

- `POST /api/ingest` — прием данных станции
- `GET /api/current` — текущий снимок
- `GET /api/chart-data?days=1` — серии для графиков
- `GET /api/uptime?hours=24` — данные uptime monitor
- `GET /api/status` — статус сервиса

## Автоуведомления Telegram

- Кнопка `Перейти на сайт` появляется в клавиатуре бота, если задан `WEATHER_SITE_URL`.
- Если станция не присылает данные дольше `TELEGRAM_STALE_MINUTES`, бот отправляет предупреждение всем `TELEGRAM_ADMIN_IDS`.
- В моменты из `TELEGRAM_DAILY_TIMES` бот отправляет текущую сводку погоды всем `TELEGRAM_DAILY_USER_IDS`.
- Если `TELEGRAM_DYNAMIC_NAME_ENABLED=1`, бот каждые `TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES` минут обновляет свое имя в формате `<TELEGRAM_DYNAMIC_NAME_PREFIX> - <T1> С`.
