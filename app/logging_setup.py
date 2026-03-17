from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from .config import LOG_DIR


def setup_logging(service_name: str) -> None:
    log_path = Path(LOG_DIR)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>" + service_name + "</cyan> | {message}",
    )
    logger.add(
        log_path / f"{service_name}.log",
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        enqueue=True,
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | " + service_name + " | {message}",
    )
