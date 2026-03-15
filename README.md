# Weather Station Dashboard

Python-приложение для приема телеметрии от метеостанции, хранения данных в SQLite, просмотра текущей погоды, графиков и истории, плюс Telegram-бот с кнопкой текущей погоды.

## Почему SQLite

Для одной домашней станции и таймсерий с умеренной частотой записи `SQLite` проще и практичнее `MongoDB`: один файл, не нужен отдельный сервер, бэкап и деплой проще. Если позже появится несколько станций и высокий поток данных, можно будет вынести хранилище в PostgreSQL без смены HTTP- и bot-логики.

## Docker

База хранится вне контейнера в папке `./data` на хосте. Внутри контейнеров она доступна как `/data/weather.sqlite3`.

## Настройки через .env

Скопируйте [.env.example](C:/Users/shkinev/project/weather.shkinev.me/.env.example) в `.env` и заполните значения.

Пример:

```bash
copy .env.example .env
```

Основные переменные:

- `WEATHER_DB_PATH=/data/weather.sqlite3`
- `TELEGRAM_BOT_TOKEN=ваш_токен`
- `NGINX_HTTP_PORT=80`
- `NGINX_HTTPS_PORT=443`

## SSL-сертификаты

Положите свои сертификаты в папку `./certs` рядом с `docker-compose.yml`.

Имена файлов должны быть строго такими:

- `./certs/shkinev_me.crt`
- `./certs/shkinev_me.key`

Внутри контейнера `nginx` они будут доступны по тем путям, которые вы указали:

- `/etc/nginx/certs/shkinev_me.crt`
- `/etc/nginx/certs/shkinev_me.key`

### Запуск веб-приложения

```bash
docker compose up -d --build
```

После запуска интерфейс будет доступен через `nginx`:

- `http://127.0.0.1` с редиректом на HTTPS
- `https://127.0.0.1` или ваш домен

### Запуск Telegram-бота

После заполнения `.env` поднимите bot-сервис:

```bash
docker compose up -d --build
```

### Остановка

```bash
docker compose down
```

## Прием данных

POST на `/api/ingest` с JSON в формате из вашего `example.json`.

Пример для Windows:

```bash
curl -X POST http://127.0.0.1:8000/api/ingest ^
  -H "Content-Type: application/json" ^
  --data "@example.json"
```

## Структура контейнеров

- `web` запускает `uvicorn app.main:app --host 0.0.0.0 --port 8000` и доступен только внутри Docker-сети
- `nginx` принимает HTTP/HTTPS, завершает TLS и проксирует запросы в `web`
- `bot` запускает `python bot.py`
- `web` и `bot` используют один и тот же bind mount `./data:/data`
