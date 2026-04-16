# Weather Station Dashboard

Приложение для приема телеметрии от метеостанции, хранения данных в SQLite, веб-аналитики и Telegram-бота.

## Состав

- `web`: FastAPI + Jinja2 + Tabler UI
- `bot`: Telegram-бот (polling)
- `data/weather.sqlite3`: база с телеметрией

## Основные возможности

- Главная страница с карточками ключевых метрик и мини-графиками
- Виджет `Комфорт/риск`
- Сравнение периодов по `T1`: сегодня vs вчера / месяц назад / год назад
- Uptime monitor
- Живой режим (автообновление)
- Отдельная страница графиков:
  - температура, влажность, давление, ветер, PM и осадки
  - тепловая карта температуры по часам
  - календарь аномалий
- Страница `Состояние станции`
- История по выбранному дню
- Telegram-бот:
  - кнопка текущей погоды
  - кнопка перехода на сайт
  - уведомления о пропаже данных
  - рассылка по расписанию
  - динамическое имя бота с текущей температурой

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните значения.

- `WEATHER_DB_PATH=/data/weather.sqlite3`
- `TELEGRAM_BOT_TOKEN=...`
- `WEB_BIND_PORT=18080`
- `WEATHER_TIMEZONE=Asia/Omsk`
- `LOG_DIR=/logs`
- `WEATHER_SITE_URL=https://weather.shkinev.me`
- `TELEGRAM_ADMIN_IDS=123456789,987654321`
- `TELEGRAM_DAILY_USER_IDS=123456789,987654321`
- `TELEGRAM_DAILY_TIMES=07:00,20:00`
- `TELEGRAM_STALE_MINUTES=10`
- `TELEGRAM_MONITOR_INTERVAL_SECONDS=120`
- `TELEGRAM_DYNAMIC_NAME_ENABLED=1`
- `TELEGRAM_DYNAMIC_NAME_PREFIX=Погода в КП "Аист"`
- `TELEGRAM_DYNAMIC_NAME_INTERVAL_MINUTES=30`

## Запуск в Docker

```bash
docker compose up -d --build
```

Логи на хосте:

- `logs/web.log`
- `logs/bot.log`

Остановка:

```bash
docker compose down
```

## Локальный запуск (Windows / PowerShell)

1. Подготовка окружения:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Переменные:

```powershell
$env:WEATHER_DB_PATH="data/weather.sqlite3"
$env:WEATHER_TIMEZONE="Asia/Omsk"
$env:LOG_DIR="logs"
```

3. Веб:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

4. Бот (в другой консоли):

```powershell
$env:WEATHER_DB_PATH="data/weather.sqlite3"
$env:WEATHER_TIMEZONE="Asia/Omsk"
$env:LOG_DIR="logs"
$env:TELEGRAM_BOT_TOKEN="ваш_токен"
py -3 bot.py
```

Сайт: `http://127.0.0.1:8000`

## API

- `POST /api/ingest` - прием данных станции
- `GET /api/current` - текущий снимок
- `GET /api/chart-data?days=1` - серии для графиков
- `GET /api/uptime?hours=24` - данные uptime monitor
- `GET /api/comfort-risk` - статус комфорта/риска
- `GET /api/period-comparison` - сравнение периодов по T1
- `GET /api/temperature-heatmap?days=30` - матрица тепловой карты
- `GET /api/anomaly-calendar?month=YYYY-MM` - календарь аномалий
- `GET /api/station-status` - состояние станции
- `GET /api/status` - статус сервиса
