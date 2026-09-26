"""Лог вызовов view в логгер web.controllers: кто, с какими данными и чем закончилось."""

import logging
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import Http404

from warehouse.common.exceptions import BusinessError

logger = logging.getLogger('web.controllers')

SECRET_PARTS = ('password', 'secret', 'token', 'csrf')
MAX_VALUE_LENGTH = 200


def _clean(key: str, values: list[str]) -> str | list[str]:
    """Значение поля для лога: секреты скрыты, длинные строки обрезаны."""
    if any(part in key.lower() for part in SECRET_PARTS):
        return '***'
    short = [v if len(v) <= MAX_VALUE_LENGTH else v[:MAX_VALUE_LENGTH] + '…' for v in values]
    return short[0] if len(short) == 1 else short


def request_data(request) -> dict:
    """Поля POST и имена загруженных файлов без секретов."""
    data = {key: _clean(key, request.POST.getlist(key)) for key in request.POST}
    for key in request.FILES:
        data[key] = [f'{f.name} ({f.size} б)' for f in request.FILES.getlist(key)]
    return data


def logged(view):
    """Пишет вход во view, бизнес-ошибку (warning), сбой (exception со стеком) и код ответа."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        match = getattr(request, 'resolver_match', None)
        name = match.view_name if match else view.__name__
        actor = getattr(request, 'actor', None)
        employee_id = actor.employee_id if actor else None
        logger.info(
            '%s %s ← employee_id=%s args=%s data=%s',
            request.method, name, employee_id, kwargs, request_data(request),
        )
        try:
            response = view(request, *args, **kwargs)
        except BusinessError as exc:
            logger.warning('%s ✗ employee_id=%s %s: %s', name, employee_id, type(exc).__name__, exc.message)
            raise
        except (Http404, PermissionDenied) as exc:
            logger.warning('%s ✗ employee_id=%s %s: %s', name, employee_id, type(exc).__name__, exc)
            raise
        except Exception:
            logger.exception('%s ✗ employee_id=%s', name, employee_id)
            raise
        logger.info('%s → %s', name, response.status_code)
        return response

    return wrapper
