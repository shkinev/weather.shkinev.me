# Weather Station Dashboard

Python-приложение для приема телеметрии от метеостанции, хранения данных в SQLite, просмотра текущей погоды, графиков и истории, плюс Telegram-бот с кнопкой текущей погоды.

## Docker-схема (без nginx в контейнере)

На сервере используется один общий Nginx на хосте, который слушает `80/443`.
Этот проект в Docker запускает только:

- `web` (FastAPI/Uvicorn)
- `bot` (Telegram polling)

Контейнер `web` публикуется только в localhost хоста:

- `127.0.0.1:${WEB_BIND_PORT:-18080} -> 8000`

Поэтому конфликта портов между проектами нет.

## Настройка через .env

Скопируйте [.env.example](C:/Users/shkinev/project/weather.shkinev.me/.env.example) в `.env` и заполните значения.

Пример:

```bash
copy .env.example .env
```

Основные переменные:

- `WEATHER_DB_PATH=/data/weather.sqlite3`
- `TELEGRAM_BOT_TOKEN=ваш_токен`
- `WEB_BIND_PORT=18080`

## Запуск

```bash
docker compose up -d --build
```

Остановка:

```bash
docker compose down
```

## Конфиг хостового Nginx

Ниже шаблон для `/etc/nginx/conf.d/weather.shkinev.me.conf` (или аналогичного файла на вашем сервере):

```nginx
upstream weather_app {
    server 127.0.0.1:18080;
}

server {
    listen 80;
    listen [::]:80;
    server_name __DOMAIN__;

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name __DOMAIN__;

    ssl_certificate /etc/nginx/certs/shkinev_me.crt;
    ssl_certificate_key /etc/nginx/certs/shkinev_me.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 20m;

    location / {
        proxy_pass http://weather_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 120s;
    }
}
```

После изменения конфига:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

## Прием данных

POST на `/api/ingest` с JSON в формате из `example.json`.

Пример для Windows:

```bash
curl -X POST http://127.0.0.1:18080/api/ingest ^
  -H "Content-Type: application/json" ^
  --data "@example.json"
```

На проде обычно отправляют в ваш домен по HTTPS:

```bash
curl -X POST https://__DOMAIN__/api/ingest ^
  -H "Content-Type: application/json" ^
  --data "@example.json"
```

## Структура контейнеров

- `web` запускает `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `bot` запускает `python bot.py`
- `web` и `bot` используют один и тот же bind mount `./data:/data`
