"""HTTP Basic Auth для /admin/*.

Источник правды:
- Если задан ADMIN_PASSWORD_HASH (bcrypt) — он используется напрямую.
- Иначе если задан ADMIN_PASSWORD — он хэшируется bcrypt'ом один раз
  на старте и хранится только в памяти процесса.
- Если ни то, ни другое — admin отключён: require_admin вернёт 503,
  а в логах будет предупреждение.
"""
from __future__ import annotations

import hmac
import secrets

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from loguru import logger

from .config import ADMIN_PASSWORD, ADMIN_PASSWORD_HASH, ADMIN_USERNAME


_security = HTTPBasic(realm="weather.shkinev.me admin")


def _resolve_hash() -> bytes | None:
    if ADMIN_PASSWORD_HASH:
        try:
            return ADMIN_PASSWORD_HASH.encode("utf-8")
        except UnicodeEncodeError:
            logger.error("ADMIN_PASSWORD_HASH is not valid utf-8; admin disabled")
            return None
    if ADMIN_PASSWORD:
        return bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt())
    return None


_PASSWORD_HASH: bytes | None = _resolve_hash()
_admin_enabled = _PASSWORD_HASH is not None

if not _admin_enabled:
    logger.warning(
        "Admin panel disabled: set ADMIN_PASSWORD or ADMIN_PASSWORD_HASH "
        "in .env to enable /admin/*"
    )


def admin_enabled() -> bool:
    return _admin_enabled


def require_admin(credentials: HTTPBasicCredentials = Depends(_security)) -> str:
    """FastAPI dependency: 401 при неправильных кредах, 503 если admin не настроен."""
    if not _admin_enabled or _PASSWORD_HASH is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin panel is disabled. Set ADMIN_PASSWORD or ADMIN_PASSWORD_HASH.",
        )

    # Сравнение пользователя — констант-тайм через secrets.compare_digest.
    user_ok = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    pass_ok = bcrypt.checkpw(credentials.password.encode("utf-8"), _PASSWORD_HASH)

    if not (user_ok and pass_ok):
        # Не давать атакующему понять, что не так — username или password.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="weather.shkinev.me admin"'},
        )

    return credentials.username
