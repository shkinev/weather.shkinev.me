# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Self-hosted weather station dashboard: ingests telemetry from a local weather station over HTTP, stores it in SQLite, and exposes a FastAPI dashboard plus a Telegram bot. UI text and most user-facing strings are in Russian. There is no test suite.

## Run / develop

Local dev (no Docker):
```bash
python3.12 -m venv .venv
source .venv/bin/activate            # POSIX / Git Bash
pip install -r requirements.txt
cp .env.example .env                 # then fill in values
mkdir -p data logs
set -a && source .env && set +a
uvicorn app.main:app --host 127.0.0.1 --port 18080 --proxy-headers --forwarded-allow-ips="*"
python bot.py                        # separate process for the Telegram bot
```

On Windows PowerShell, `Activate.ps1` may be blocked by the default execution policy. Skip activation and call the venv's interpreter directly — it works the same:
```powershell
$env:WEATHER_DB_PATH = "$PWD\data\weather.sqlite3"
$env:LOG_DIR = "$PWD\logs"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18080 --proxy-headers --forwarded-allow-ips="*"
```

Docker (the deploy target):
```bash
docker compose up -d --build
docker compose logs -f web
docker compose logs -f bot
```

The web container listens on `8000` internally and is published on `127.0.0.1:${WEB_BIND_PORT:-18080}`. Nginx on the host terminates TLS and proxies to that port (see `deploy/nginx/weather.conf.example`).

Quick health checks:
```bash
curl http://127.0.0.1:18080/api/status
curl http://127.0.0.1:18080/api/current
```

## Architecture

Two long-running processes share one SQLite file (`WEATHER_DB_PATH`):

- **Web** ([app/main.py](app/main.py)) — FastAPI app. Calls `init_db()` on startup, mounts `/static`, renders Jinja2 templates from [app/templates/](app/templates/), and exposes both HTML pages (`/`, `/charts`, `/history`, `/station`) and JSON APIs (`/api/ingest`, `/api/current`, `/api/chart-data`, `/api/uptime`, `/api/comfort-risk`, `/api/period-comparison`, `/api/temperature-heatmap`, `/api/anomaly-calendar`, `/api/station-status`).
- **Bot** ([bot.py](bot.py)) — `python-telegram-bot` Application. On start it spawns three asyncio loops alongside the polling updater: `stale_data_monitor_loop` (alerts admins when no fresh telemetry), `daily_weather_broadcast_loop` (sends snapshots at `TELEGRAM_DAILY_TIMES`), and `dynamic_bot_name_loop` (rewrites the bot's display name with the current temperature). The bot reads from the same DB the web writes to — there is no IPC.

Ingest flow: a device POSTs `{"devices": [{"mac": "...", "sensors": [{"id": "T1", "value": 23.4, "unit": "°C"}, ...]}, ...]}` to `/api/ingest`. `save_payload` writes one `ingest_batches` row per device and one `observations` row per numeric sensor reading. `received_at` is the server's UTC ingest time, not a device timestamp.

### Data model

Two tables, defined inline in `init_db()` in [app/db.py](app/db.py):

- `ingest_batches(id, device_mac, received_at, payload_json)` — raw payload archive, one row per device per POST.
- `observations(id, batch_id, device_mac, observed_at, sensor_id, sensor_name, value, unit)` — flattened readings. `sensor_id` is uppercased on write; `sensor_name`/`unit` are resolved through [app/sensor_map.py](app/sensor_map.py) at write time and stored denormalized.

Indexed by `(sensor_id, observed_at DESC)` and `(device_mac, observed_at DESC)`. WAL is enabled. All timestamps are stored as ISO-8601 UTC strings; conversion to `WEATHER_TIMEZONE` happens at read time via `to_local_timestamp()`.

### app/db.py is the analytics layer

[app/db.py](app/db.py) (~1000 lines) holds **all** SQL plus the derived metrics consumed by the dashboard widgets and the bot: `get_latest_snapshot`, `get_chart_series`, `get_history_for_date`, `get_uptime_monitor`, `get_today_extremes` (generic, picks first sensor with data from a list), `get_today_temperature_extremes` (thin wrapper), `get_comfort_risk`, `get_period_comparison` (returns both day/night aggregates and `series.{today,yesterday,monthAgo}` hourly arrays for the overlay sparkline), `get_temperature_heatmap`, `get_anomaly_calendar`, `get_station_status`, `format_telegram_snapshot`. New widgets/endpoints belong here, not in `main.py`. Sensor-ID groupings (`TEMPERATURE_SENSOR_IDS`, `HUMIDITY_SENSOR_IDS`, `PRESSURE_SENSOR_IDS`) are defined at the top of the file and used to fall back across redundant sensors (e.g. T1→T2→…) — preserve that ordering when changing them.

### Sensor catalog

[app/sensor_map.py](app/sensor_map.py) is the source of truth for human-readable sensor labels and units. `PRIMARY_SENSOR_IDS` controls which readings appear in the dashboard's "primary" row and the Telegram summary. Adding a new sensor type means adding it here; unknown IDs flow through with the raw ID as the label and no unit.

### Config and runtime

[app/config.py](app/config.py) reads everything from environment variables (no settings file). Defaults are baked in for everything except `TELEGRAM_BOT_TOKEN` (required only by the bot, which raises on startup if missing) and `WEATHER_SITE_URL` (used to render the "Open site" button in Telegram). `WEATHER_TIMEZONE` defaults to `UTC`; both `app/main.py` and `app/db.py` independently fall back to UTC if the zone can't be loaded.

[app/logging_setup.py](app/logging_setup.py) configures Loguru per-service. Each entrypoint calls `setup_logging("web")` or `setup_logging("bot")` to write to `LOG_DIR/{web,bot}.log` with 10MB rotation and 14-day retention.

### Frontend

Server-rendered Jinja2 with a custom design system in [app/static/dashboard.css](app/static/dashboard.css) — `oklch` palette, light/dark theme on `data-bs-theme`, dense-grid dashboard ported from a Claude Design handoff (variation A "плотная сетка"). Tabler is **not** used — only `tabler-icons.min.css` for the theme-toggle glyph. Chart.js still powers the line graphs on `/charts`; everywhere else (sparklines, comfort gauge, min/max bars, period overlay) charts are inline SVG drawn by the small JS in `index.html`.

[app/templates/base.html](app/templates/base.html) renders the topbar (brand + nav + theme toggle), wraps `{% block content %}` in `<div class="dashboard">`, and ships the optional Yandex.Metrika tag (enabled iff `YANDEX_METRIKA_ID` is set). All four pages (`index`, `charts`, `history`, `station`) extend it and use the shared classes (`.card`, `.page-header`, `.seg`, `.data-table`, `.kpi-value`, `.alert-{good,warn,bad}`).

Inter and JetBrains Mono are loaded from Google Fonts CDN; everything else (Tabler icons, Chart.js) is vendored in `app/static/vendor/`. When bumping vendored versions, also update the table in [README.md](README.md).

`render_template()` in [app/main.py](app/main.py) wraps `TemplateResponse` to support both the request-first and name-first signatures across Starlette versions — keep using it instead of calling `templates.TemplateResponse` directly.

**Jinja gotcha:** when looping to find the first available sensor, use `{% set ns = namespace(found=none) %}` and assign to `ns.found` inside the loop. A plain `{% set foo = ... %}` inside `{% for %}` only lives in the loop's scope and is `None` outside it (this caused current-value cards to render `—` once already).

## Conventions

- Russian is the user-facing language (templates, bot replies, log messages, comfort-risk reasons, relative-age strings like "5 мин назад"). Keep new user-visible strings in Russian.
- Timestamps: store UTC ISO strings, convert to local only for display.
- Sensor IDs are uppercase everywhere after ingest — compare with `.upper()` and define new groupings in `sensor_map.py`/`db.py` in uppercase.
- Don't commit `data/weather.sqlite3`, `.env`, or anything in `logs/` (already in `.gitignore`).
