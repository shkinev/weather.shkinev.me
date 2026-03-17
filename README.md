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
py -3 bot.py
```

## API

- `POST /api/ingest` — прием данных станции
- `GET /api/current` — текущий снимок
- `GET /api/chart-data?days=1` — серии для графиков
- `GET /api/uptime?hours=24` — данные uptime monitor
- `GET /api/status` — статус сервиса
