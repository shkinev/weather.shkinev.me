from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from .config import APP_TITLE, SITE_BRAND, WEATHER_TIMEZONE, YANDEX_METRIKA_ENABLED, YANDEX_METRIKA_ID
from .db import (
    get_anomaly_calendar,
    get_chart_series,
    get_comfort_risk,
    get_history_for_date,
    get_latest_snapshot,
    get_period_comparison,
    get_station_status,
    get_temperature_heatmap,
    get_today_temperature_extremes,
    get_uptime_monitor,
    init_db,
    save_payload,
)
from .logging_setup import setup_logging


app = FastAPI(title=APP_TITLE, version="1.1.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["app_title"] = APP_TITLE
templates.env.globals["site_brand"] = SITE_BRAND
templates.env.globals["yandex_metrika_enabled"] = YANDEX_METRIKA_ENABLED
templates.env.globals["yandex_metrika_id"] = YANDEX_METRIKA_ID
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
try:
    APP_TZ = ZoneInfo(WEATHER_TIMEZONE)
except ZoneInfoNotFoundError:
    APP_TZ = UTC


def render_template(request: Request, template_name: str, context: dict[str, Any]) -> HTMLResponse:
    full_context = {"request": request, **context}
    try:
        # Starlette/FastAPI with request-first TemplateResponse signature.
        return templates.TemplateResponse(request=request, name=template_name, context=full_context)
    except TypeError:
        # Backward compatibility for name-first signature.
        return templates.TemplateResponse(template_name, full_context)


@app.on_event("startup")
def on_startup() -> None:
    setup_logging("web")
    init_db()
    logger.info("Web service started")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("HTTP {} {}", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error on {} {}", request.method, request.url.path)
        raise
    logger.info("HTTP {} {} -> {}", request.method, request.url.path, response.status_code)
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    snapshot = get_latest_snapshot()
    uptime = get_uptime_monitor(24)
    temp_extremes = get_today_temperature_extremes()
    comfort = get_comfort_risk(snapshot)
    comparison = get_period_comparison()
    return render_template(
        request,
        "index.html",
        {
            "snapshot": snapshot,
            "uptime": uptime,
            "temp_extremes": temp_extremes,
            "comfort": comfort,
            "comparison": comparison,
        },
    )


@app.get("/charts", response_class=HTMLResponse)
def charts_page(request: Request, days: int = 1) -> HTMLResponse:
    period = max(1, min(days, 90))
    return render_template(request, "charts.html", {"days": period})


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, day: str | None = None) -> HTMLResponse:
    selected_day = day or datetime.now(APP_TZ).date().isoformat()
    items = get_history_for_date(selected_day)
    return render_template(request, "history.html", {"selected_day": selected_day, "items": items})


@app.get("/station", response_class=HTMLResponse)
def station_page(request: Request) -> HTMLResponse:
    status = get_station_status()
    return render_template(request, "station.html", {"status": status})


@app.post("/api/ingest")
async def ingest(payload: dict[str, Any]) -> JSONResponse:
    devices = payload.get("devices")
    if not isinstance(devices, list) or not devices:
        raise HTTPException(status_code=400, detail="Payload must contain a non-empty 'devices' array.")

    result = save_payload(payload)
    return JSONResponse({"status": "ok", **result})


@app.get("/api/status")
def api_status() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/api/current")
def current_weather() -> JSONResponse:
    snapshot = get_latest_snapshot()
    if not snapshot:
        return JSONResponse({"status": "empty", "snapshot": None})
    return JSONResponse({"status": "ok", "snapshot": snapshot})


@app.get("/api/chart-data")
def chart_data(days: int = 1) -> JSONResponse:
    return JSONResponse(get_chart_series(days))


@app.get("/api/uptime")
def api_uptime(hours: int = 24) -> JSONResponse:
    return JSONResponse(get_uptime_monitor(hours))


@app.get("/api/comfort-risk")
def api_comfort_risk() -> JSONResponse:
    return JSONResponse(get_comfort_risk())


@app.get("/api/period-comparison")
def api_period_comparison() -> JSONResponse:
    return JSONResponse(get_period_comparison())


@app.get("/api/temperature-heatmap")
def api_temperature_heatmap(days: int = 30) -> JSONResponse:
    return JSONResponse(get_temperature_heatmap(days))


@app.get("/api/anomaly-calendar")
def api_anomaly_calendar(month: str | None = None) -> JSONResponse:
    return JSONResponse(get_anomaly_calendar(month))


@app.get("/api/station-status")
def api_station_status() -> JSONResponse:
    return JSONResponse(get_station_status())


def _favicon_temp(snapshot: dict[str, Any] | None) -> float | None:
    if not snapshot:
        return None
    for sensor_id in ("T1", "T2", "T3", "T4", "T5", "T6"):
        for reading in snapshot.get("readings", []):
            if str(reading.get("sensor_id", "")).upper() == sensor_id:
                try:
                    return float(reading["value"])
                except (TypeError, ValueError, KeyError):
                    return None
    return None


@app.get("/favicon.ico")
def favicon_ico() -> RedirectResponse:
    return RedirectResponse(url="/favicon.svg", status_code=307)


@app.get("/favicon.svg")
def favicon_svg() -> Response:
    temp = _favicon_temp(get_latest_snapshot())
    if temp is None:
        label = "--"
        bg = "#334155"
    elif temp < 0:
        label = f"{temp:.0f}"
        bg = "#2563eb"
    elif temp < 20:
        label = f"{temp:.0f}"
        bg = "#0ea5e9"
    elif temp < 30:
        label = f"{temp:.0f}"
        bg = "#f59e0b"
    else:
        label = f"{temp:.0f}"
        bg = "#ef4444"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<rect x="2" y="2" width="60" height="60" rx="14" fill="{bg}"/>
<text x="32" y="39" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#ffffff">{label}</text>
</svg>"""
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
