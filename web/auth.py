"""Кто вошёл: токен в сессии, request.actor и проверка прав для шаблонов."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from warehouse.bll.interfaces.auth_service import TokenDTO, TokenPayloadDTO
from warehouse.common.dto import WarehouseDTO
from warehouse.common.exceptions import AuthError

from .services import login_service

SESSION_TOKEN = 'token'


def sign_in(request, token: TokenDTO, warehouse: WarehouseDTO) -> None:
    """Кладёт токен и данные для шапки в новую сессию, которая живёт не дольше токена."""
    request.session.cycle_key()
    request.session[SESSION_TOKEN] = token.access_token
    request.session['employee_name'] = token.employee.full_name
    request.session['warehouse_title'] = warehouse.title
    request.session.set_expiry(token.expires_at)


def sign_out(request) -> None:
    request.session.flush()


def authenticate(request) -> TokenPayloadDTO | None:
    """Проверяет токен из сессии и кладёт результат в request.actor."""
    token = request.session.get(SESSION_TOKEN)
    if not token:
        return None
    try:
        request.actor = login_service().decode_token(token)
    except AuthError:
        sign_out(request)
        return None
    return request.actor


def employee_required(view):
    """Пускает только вошедшего сотрудника, остальных отправляет на /login/."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        had_token = SESSION_TOKEN in request.session
        if authenticate(request) is not None:
            return view(request, *args, **kwargs)
        if had_token:
            messages.error(request, 'Сессия истекла, войдите заново')
        if request.method != 'GET':
            return redirect('login')
        query = urlencode({REDIRECT_FIELD_NAME: request.get_full_path()})
        return redirect(f"{reverse('login')}?{query}")

    return wrapper


def api_employee_required(view):
    """Как employee_required, но для JSON: без входа отвечает 401."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if authenticate(request) is None:
            return JsonResponse({'error': 'Войдите в систему'}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


<<<<<<< HEAD
def can(request, permission) -> bool:
    """Есть ли у вошедшего право из БД (RolePermissions → JWT → request.actor.permissions)."""
    actor = getattr(request, 'actor', None)
    if actor is None:
        return False
    name = getattr(permission, 'value', permission)
    return name in actor.permissions
=======
def can(request, permission: str) -> bool:
    """Есть ли у вошедшего сотрудника право; нужно, чтобы прятать кнопки."""
    actor = getattr(request, 'actor', None)
    return actor is not None and permission in actor.permissions
>>>>>>> main
