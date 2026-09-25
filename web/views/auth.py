from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from warehouse.common.exceptions import BusinessError

from ..auth import authenticate, employee_required, sign_in, sign_out
from ..errors import business_errors_as_http
from ..forms import RegisterForm
from ..services import employee_service, login_service


def _safe_next(request, url: str) -> str:
    if url and url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return 'home'


@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Страница входа по логину и паролю."""
    if request.method == 'GET' and authenticate(request) is not None:
        return redirect('home')

    next_url = request.POST.get('next') or request.GET.get(REDIRECT_FIELD_NAME, '')
    context = {'login': '', 'error': None, 'next': next_url}

    if request.method == 'POST':
        context['login'] = request.POST.get('login', '').strip()
        try:
            token = login_service().login(context['login'], request.POST.get('password', ''))
            warehouse = employee_service().get_warehouse(token.employee.id)
        except BusinessError as e:
            context['error'] = e.message
        else:
            sign_in(request, token, warehouse)
            return redirect(_safe_next(request, next_url))

    return render(request, 'web/auth/login.html', context)


@require_POST
def logout_view(request):
    """Выход: сессия очищается целиком."""
    sign_out(request)
    return redirect('login')


@require_http_methods(['GET', 'POST'])
@employee_required
@business_errors_as_http
def register_view(request):
    """Регистрация сотрудника администратором."""
    admin_id = request.actor.employee_id
    service = employee_service()
    options = {'warehouses': service.list_warehouses(admin_id), 'roles': service.list_roles(admin_id)}
    error = None

    if request.method == 'POST':
        form = RegisterForm(request.POST, **options)
        if form.is_valid():
            try:
                employee = service.register(admin_id, form.to_new_employee())
            except BusinessError as e:
                error = e.message
            else:
                messages.success(request, f'Сотрудник {employee.full_name} зарегистрирован, логин «{employee.login}»')
                return redirect('employee_new')
    else:
        form = RegisterForm(**options)

    return render(request, 'web/auth/register.html', {'form': form, 'error': error})
