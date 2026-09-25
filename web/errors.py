"""Перевод бизнес-ошибок BLL в ответы сайта."""

from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from warehouse.common.exceptions import AccessDeniedError, BusinessError, NotFoundError


def business_errors_as_http(view):
    """Для страниц (GET): NotFoundError -> 404, AccessDeniedError -> 403."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except NotFoundError as e:
            raise Http404(e.message) from e
        except AccessDeniedError as e:
            raise PermissionDenied(e.message) from e

    return wrapper


def business_errors_as_messages(view):
    """Для кнопок (POST): текст BusinessError в messages.error и редирект назад."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except BusinessError as e:
            messages.error(request, e.message)
            return redirect_back(request)

    return wrapper


def redirect_back(request, fallback: str = 'home'):
    """Редирект на страницу, с которой пришёл запрос, или на fallback."""
    referer = request.META.get('HTTP_REFERER')
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(referer)
    return redirect(fallback)
