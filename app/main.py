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

from .config import WEATHER_TIMEZONE
from .db import get_chart_series, get_history_for_date, get_latest_snapshot, get_uptime_monitor, init_db, save_payload
from .logging_setup import setup_logging


app = FastAPI(title="Weather Station", version="1.0.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
try:
    APP_TZ = ZoneInfo(WEATHER_TIMEZONE)
except ZoneInfoNotFoundError:
    APP_TZ = UTC


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
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "snapshot": snapshot,
            "uptime": uptime,
        },
    )


@app.get("/charts", response_class=HTMLResponse)
def charts_page(request: Request, days: int = 1) -> HTMLResponse:
    period = max(1, min(days, 90))
    return templates.TemplateResponse(
        "charts.html",
        {"request": request, "days": period},
    )


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, day: str | None = None) -> HTMLResponse:
    selected_day = day or datetime.now(APP_TZ).date().isoformat()
    items = get_history_for_date(selected_day)
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "selected_day": selected_day, "items": items},
    )


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
