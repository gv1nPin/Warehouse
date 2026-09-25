from datetime import datetime, timedelta, timezone
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from warehouse.bll.interfaces.auth_service import TokenDTO, TokenPayloadDTO
from warehouse.common import PermissionName
from warehouse.common.dto import EmployeeDTO, RoleDTO, WarehouseDTO
from warehouse.common.exceptions import AccessDeniedError, AuthError, ValidationError

from .services import container

EMPLOYEE = EmployeeDTO(
    id=7, first_name='Иван', last_name='Петров', login='petrov',
    role_id=3, role_name='Администратор системы', warehouse_id=1, is_deleted=False,
)
WAREHOUSE = WarehouseDTO(id=1, title='Склад Север', address='ул. Ленина, 1')


def payload(*permissions: str) -> TokenPayloadDTO:
    return TokenPayloadDTO(
        employee_id=EMPLOYEE.id, warehouse_id=1, role_name=EMPLOYEE.role_name,
        permissions=frozenset(permissions), expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


class WebTestCase(TestCase):
    """Подменяет сервисы BLL, чтобы проверять сайт без PostgreSQL."""

    def setUp(self):
        self.login = mock.Mock()
        self.login.login.return_value = TokenDTO(
            access_token='tok', token_type='bearer',
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1), employee=EMPLOYEE,
        )
        self.login.decode_token.return_value = payload(PermissionName.EMPLOYEE_MANAGE)
        self.employees = mock.Mock()
        self.employees.get_warehouse.return_value = WAREHOUSE
        self.employees.list_warehouses.return_value = [WAREHOUSE]
        self.employees.list_roles.return_value = [RoleDTO(id=6, name='Водитель')]

        for provider, service in ((container.login_service, self.login), (container.employee_service, self.employees)):
            provider.override(service)
            self.addCleanup(provider.reset_override)

    def sign_in(self):
        return self.client.post(reverse('login'), {'login': 'petrov', 'password': 'secret'})


class LoginTests(WebTestCase):
    def test_anonymous_is_redirected_to_login_with_next(self):
        response = self.client.get(reverse('stock'))
        self.assertRedirects(response, f"{reverse('login')}?next=/stock/", fetch_redirect_response=False)

    def test_login_puts_token_in_session_and_shows_header(self):
        self.assertRedirects(self.sign_in(), reverse('home'), fetch_redirect_response=False)
        self.assertEqual(self.client.session['token'], 'tok')
        page = self.client.get(reverse('home'))
        self.assertContains(page, 'Петров Иван')
        self.assertContains(page, 'Склад Север')
        self.assertContains(page, 'Новый сотрудник')

    def test_wrong_password_keeps_login(self):
        self.login.login.side_effect = AuthError('Неверный логин или пароль')
        page = self.sign_in()
        self.assertContains(page, 'Неверный логин или пароль')
        self.assertContains(page, 'value="petrov"')

    def test_next_to_other_host_is_ignored(self):
        response = self.client.post(
            reverse('login'), {'login': 'petrov', 'password': 'x', 'next': 'https://evil.example/'}
        )
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_expired_token_sends_back_to_login(self):
        self.sign_in()
        self.login.decode_token.side_effect = AuthError('Сессия истекла, войдите заново')
        response = self.client.get(reverse('home'))
        self.assertTrue(response.url.startswith(reverse('login')))
        self.assertNotIn('token', self.client.session)

    def test_logout_clears_session(self):
        self.sign_in()
        self.assertRedirects(self.client.post(reverse('logout')), reverse('login'), fetch_redirect_response=False)
        self.assertNotIn('token', self.client.session)


class RegisterTests(WebTestCase):
    form = {
        'last_name': 'Сидоров', 'first_name': 'Пётр', 'login': 'sidorov',
        'password': 'password1', 'password_repeat': 'password1', 'warehouse_id': '1', 'role_id': '6',
    }

    def test_admin_registers_employee(self):
        self.sign_in()
        self.employees.register.return_value = EMPLOYEE
        response = self.client.post(reverse('employee_new'), self.form)
        self.assertRedirects(response, reverse('employee_new'), fetch_redirect_response=False)
        new = self.employees.register.call_args.args[1]
        self.assertEqual((new.login, new.warehouse_id, new.role_id), ('sidorov', 1, 6))

    def test_passwords_must_match(self):
        self.sign_in()
        page = self.client.post(reverse('employee_new'), {**self.form, 'password_repeat': 'other'})
        self.assertContains(page, 'Пароли не совпадают')
        self.assertContains(page, 'value="sidorov"')
        self.employees.register.assert_not_called()

    def test_service_error_is_shown_over_form(self):
        self.sign_in()
        self.employees.register.side_effect = ValidationError('Логин «sidorov» уже занят')
        self.assertContains(self.client.post(reverse('employee_new'), self.form), 'Логин «sidorov» уже занят')

    def test_not_admin_gets_403(self):
        self.login.decode_token.return_value = payload(PermissionName.SHIPMENT_CREATE)
        self.employees.list_warehouses.side_effect = AccessDeniedError('Недостаточно прав для этого действия')
        self.sign_in()
        response = self.client.get(reverse('employee_new'))
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(self.client.get(reverse('home')), 'Новый сотрудник')


class StubAndTagTests(WebTestCase):
    def test_every_stub_page_opens(self):
        self.sign_in()
        for name, kwargs in (('home', {}), ('stock', {}), ('shipments', {}), ('draft_new', {}),
                             ('shipment_detail', {'shipment_id': 1}), ('receipt', {})):
            self.assertContains(self.client.get(reverse(name, kwargs=kwargs)), 'в разработке')

    def test_stub_button_redirects_back_with_message(self):
        self.sign_in()
        response = self.client.post(reverse('stage_reserve', kwargs={'stage_id': 3}), HTTP_REFERER='/shipments/1/')
        self.assertRedirects(response, '/shipments/1/', fetch_redirect_response=False)

    def test_api_without_login_is_401(self):
        self.assertEqual(self.client.get(reverse('api_stock')).status_code, 401)

    def test_tags(self):
        from django.template import Context, Template

        html = Template(
            "{% load warehouse_tags %}{% status_pill s %}|{{ q|qty:'т' }}|{{ n|qty:'шт' }}"
        ).render(Context({'s': 'Черновик (Draft)', 'q': '1234.5', 'n': 12}))
        self.assertEqual(html, '<span class="pill st-draft">Черновик</span>|1\xa0234,500 т|12 шт')
