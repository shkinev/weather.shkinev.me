"""Простой in-memory TTL-кэш для тяжёлых аналитических функций.

Использование:
    from .cache import cached, invalidate

    @cached(ttl_seconds=300)
    def heavy_function(arg1, arg2): ...

После save_payload вызываем invalidate(), чтобы пересчёты не отдавали
устаревшие агрегаты на фоне свежеингестенных данных.

Кэш — глобальный в процессе. Не подходит для многопроцессного развёртывания
(uvicorn --workers >1 / gunicorn). При переходе на multi-worker — заменить
на Redis или подобное.
"""
from __future__ import annotations

import functools
import threading
from time import monotonic
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_store: dict[tuple[str, tuple[Any, ...], frozenset[tuple[str, Any]]], tuple[float, Any]] = {}
_lock = threading.Lock()


def _make_key(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple:
    # connection-объекты не должны попадать в ключ кэша: они меняются от запроса
    # к запросу, иначе кэш всегда мисс.
    safe_kwargs = {k: v for k, v in kwargs.items() if k != "conn"}
    safe_args = args
    try:
        return (name, safe_args, frozenset(safe_kwargs.items()))
    except TypeError:
        # Если ключи невыхешируемы — не кэшируем (ключ collision-prone).
        return (name, repr(safe_args), repr(sorted(safe_kwargs.items())))


def cached(ttl_seconds: float) -> Callable[[F], F]:
    """Декоратор: кэширует результат функции на ttl_seconds.

    Игнорирует kwarg `conn` при формировании ключа (см. выше).
    """
    def decorator(fn: F) -> F:
        name = f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _make_key(name, args, kwargs)
            now = monotonic()
            with _lock:
                hit = _store.get(key)
                if hit and (now - hit[0]) < ttl_seconds:
                    return hit[1]
            value = fn(*args, **kwargs)
            with _lock:
                _store[key] = (now, value)
            return value

        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def invalidate() -> None:
    """Сбрасывает весь кэш. Вызывается после save_payload."""
    with _lock:
        _store.clear()


def stats() -> dict[str, int]:
    """Размер кэша (для дебага)."""
    with _lock:
        return {"entries": len(_store)}
