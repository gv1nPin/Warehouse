"""
Логирование контроллеров на границе web → DTO → BLL.

Стиль как в BLL (logging.info / warning / exception), логгер:
  web.controllers

Что пишем:
  - вход: employee_id, имя операции, ключевые поля DTO (без паролей);
  - успех: краткий итог (id сущности, статус, число позиций);
  - BusinessError: warning с message;
  - прочее: exception со стеком.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from functools import wraps
from typing import Any

logger = logging.getLogger("web.controllers")

# поля, которые никогда не пишем в лог
_REDACT_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "authorization",
        "csrfmiddlewaretoken",
    }
)


def _safe(value: Any, *, depth: int = 0) -> Any:
    """Сериализация для лога: dataclass → dict, Decimal → str, обрезка вложенности."""
    if depth > 4:
        return "…"
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, str) and len(value) > 200:
            return value[:200] + "…"
        return value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        try:
            return _safe(asdict(value), depth=depth + 1)
        except Exception:
            return repr(value)
    if isinstance(value, Mapping):
        out = {}
        for k, v in value.items():
            key = str(k)
            if key.lower() in _REDACT_KEYS:
                out[key] = "***"
            else:
                out[key] = _safe(v, depth=depth + 1)
        return out
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value)
        if len(items) > 30:
            return [_safe(x, depth=depth + 1) for x in items[:30]] + [f"… +{len(items) - 30}"]
        return [_safe(x, depth=depth + 1) for x in items]
    if hasattr(value, "name") and hasattr(value, "size"):
        # UploadedFile-like
        return {"name": getattr(value, "name", None), "size": getattr(value, "size", None)}
    return repr(value)


def dto_preview(obj: Any) -> Any:
    """Публичная обёртка для логов: безопасный снимок DTO / dict / списка."""
    return _safe(obj)


def log_bll_call(
    operation: str,
    *,
    employee_id: int | None = None,
    **payload: Any,
) -> None:
    """Вход в BLL: операция + employee + поля DTO."""
    body = {k: _safe(v) for k, v in payload.items() if k.lower() not in _REDACT_KEYS}
    logger.info(
        "BLL ← %s | employee_id=%s | in=%s",
        operation,
        employee_id,
        body if body else "{}",
    )


def log_bll_ok(operation: str, result: Any = None, **extra: Any) -> None:
    """Успешный ответ BLL."""
    preview = _safe(result) if result is not None else None
    extra_s = {k: _safe(v) for k, v in extra.items()}
    if preview is not None and extra_s:
        logger.info("BLL → %s OK | out=%s | %s", operation, preview, extra_s)
    elif preview is not None:
        logger.info("BLL → %s OK | out=%s", operation, preview)
    elif extra_s:
        logger.info("BLL → %s OK | %s", operation, extra_s)
    else:
        logger.info("BLL → %s OK", operation)


def log_bll_error(operation: str, exc: BaseException, *, employee_id: int | None = None) -> None:
    """Ошибка на границе BLL."""
    message = getattr(exc, "message", None) or str(exc)
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    # BusinessError и доменные — warning; остальное — exception со стеком
    if name.endswith("Error") and "Business" in name or name in {
        "ValidationError",
        "NotFoundError",
        "AccessDeniedError",
        "InvalidStatusError",
        "BusinessError",
    }:
        logger.warning(
            "BLL → %s FAIL | employee_id=%s | %s: %s | status=%s",
            operation,
            employee_id,
            name,
            message,
            status,
        )
    else:
        logger.exception(
            "BLL → %s ERROR | employee_id=%s | %s: %s",
            operation,
            employee_id,
            name,
            message,
        )


def bll_logged(operation: str) -> Callable:
    """
    Декоратор для методов view, где первый осмысленный аргумент — request.
    Логирует старт по session employee_id; ошибки BLL — через log_bll_error.
    Ручные log_bll_call / log_bll_ok внутри метода всё равно полезны для DTO.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(self, request, *args, **kwargs):
            employee_id = None
            try:
                employee_id = request.session.get("employee_id")
            except Exception:
                pass
            logger.debug(
                "controller %s | method=%s path=%s employee_id=%s args=%s",
                operation,
                getattr(request, "method", "?"),
                getattr(request, "path", "?"),
                employee_id,
                {k: _safe(v) for k, v in kwargs.items()},
            )
            try:
                return fn(self, request, *args, **kwargs)
            except Exception as exc:
                # если view сам не поймал — зафиксируем
                log_bll_error(operation, exc, employee_id=employee_id)
                raise

        return wrapper

    return decorator
