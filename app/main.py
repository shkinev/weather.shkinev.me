from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .db import get_chart_series, get_history_for_date, get_latest_snapshot, init_db, save_payload


app = FastAPI(title="Weather Station", version="1.0.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    snapshot = get_latest_snapshot()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "snapshot": snapshot,
            "updated_at": snapshot["received_at"] if snapshot else None,
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
    selected_day = day or datetime.now(UTC).date().isoformat()
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


@app.get("/api/current")
def current_weather() -> JSONResponse:
    snapshot = get_latest_snapshot()
    if not snapshot:
        return JSONResponse({"status": "empty", "snapshot": None})
    return JSONResponse({"status": "ok", "snapshot": snapshot})


@app.get("/api/chart-data")
def chart_data(days: int = 1) -> JSONResponse:
    return JSONResponse(get_chart_series(days))
