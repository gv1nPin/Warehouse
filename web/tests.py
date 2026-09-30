import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from warehouse.bll.interfaces.auth_service import TokenDTO, TokenPayloadDTO
from warehouse.common import OperationType, PermissionName, StatusName
from warehouse.common.dto import (
    EmployeeDTO,
    OperationHistoryDTO,
    RoleDTO,
    ShipmentDTO,
    StageDocumentDTO,
    StageDTO,
    StageItemDTO,
    StockItemDTO,
    WarehouseDTO,
)
from warehouse.common.exceptions import AccessDeniedError, AuthError, ValidationError

from .controller_logging import request_data
from .services import container
from .views.shipments import apply_filters, parse_filters

P = PermissionName
SENIOR = (P.SHIPMENT_CREATE, P.SHIPMENT_DISPATCH, P.SHIPMENT_ACCEPT)
KEEPER = (P.SHIPMENT_DISPATCH, P.SHIPMENT_ACCEPT)
MANAGER = (P.SHIPMENT_CANCEL, P.SHIPMENT_VIEW_ALL)
ADMIN = tuple(PermissionName)
DRIVER = ()

EMPLOYEE = EmployeeDTO(
    id=7, first_name='Иван', last_name='Петров', login='petrov',
    role_id=3, role_name='Администратор системы', warehouse_id=1, is_deleted=False,
)
WAREHOUSE = WarehouseDTO(id=1, title='Склад Север', address='ул. Ленина, 1')
SOUTH = WarehouseDTO(id=2, title='Склад Юг', address='ул. Южная, 2')
NOW = datetime(2026, 9, 25, 8, 15, tzinfo=timezone.utc)


def payload(*permissions: str) -> TokenPayloadDTO:
    return TokenPayloadDTO(
        employee_id=EMPLOYEE.id, warehouse_id=1, role_name=EMPLOYEE.role_name,
        permissions=frozenset(permissions), expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


def item(item_id=1, document='10', actual=None, comment=None, name='Цемент М500') -> StageItemDTO:
    return StageItemDTO(
        id=item_id, stage_id=1, product_id=item_id, article_number=f'ART-{item_id}', product_name=name,
        measurement_name='т', document_quantity=Decimal(document),
        actual_quantity=None if actual is None else Decimal(actual), comment=comment,
    )


def stage(stage_id=1, shipment_id=100, order=1, status=StatusName.DRAFT, from_wh=WAREHOUSE, to_wh=SOUTH,
          driver_id=None, driver_name=None, creator_id=7, creator_name='Петров Иван', items=()) -> StageDTO:
    return StageDTO(
        id=stage_id, shipment_id=shipment_id, stage_order=order, status_id=1, status_name=status,
        shipment_status_id=1, shipment_status_name=status, planned_date=date(2026, 10, 1),
        creator_id=creator_id, creator_name=creator_name, from_warehouse=from_wh, to_warehouse=to_wh,
        driver_id=driver_id, driver_name=driver_name, acceptor_id=None, sent_at=None, received_at=None,
        items=tuple(items),
    )


def shipment(*stages: StageDTO, status=StatusName.DRAFT) -> ShipmentDTO:
    return ShipmentDTO(
        id=stages[0].shipment_id, status_id=1, status_name=status, planned_date=date(2026, 10, 1),
        created_at=NOW, creator_id=7, creator_name='Петров Иван', stages=stages,
    )


def document(document_id=5, stage_id=1, path='stage_documents/x.pdf') -> StageDocumentDTO:
    return StageDocumentDTO(
        id=document_id, stage_id=stage_id, file_name='ТОРГ-12.pdf', storage_path=path, content_type='application/pdf',
        size_bytes=1024, uploaded_by=7, uploaded_by_name='Петров Иван', uploaded_at=NOW,
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
        self.routes = mock.Mock()
        self.routes.list_routes.return_value = []
        self.routes.list_documents.return_value = []
        self.receipt = mock.Mock()
        self.receipt.get_incoming.return_value = []
        self.draft = mock.Mock()
        self.draft.list_warehouses.return_value = [WAREHOUSE, SOUTH]
        self.draft.list_available_stock.return_value = []
        self.draft.list_drivers.return_value = []
        self.dispatch = mock.Mock()
        self.stock = mock.Mock()
        self.history = mock.Mock()

        for provider, service in (
            (container.login_service, self.login),
            (container.employee_service, self.employees),
            (container.query_service, self.routes),
            (container.receive_service, self.receipt),
            (container.draft_service, self.draft),
            (container.dispatch_service, self.dispatch),
            (container.stock_query, self.stock),
            (container.history_service, self.history),
        ):
            provider.override(service)
            self.addCleanup(provider.reset_override)

    def sign_in(self, permissions=None):
        if permissions is not None:
            self.login.decode_token.return_value = payload(*permissions)
        return self.client.post(reverse('login'), {'login': 'petrov', 'password': 'secret'})

    def messages(self, response) -> list[str]:
        return [str(m) for m in response.wsgi_request._messages]


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
        'password': 'password1', 'warehouse_id': '1', 'role_id': '6',
    }

    def test_admin_registers_employee(self):
        self.sign_in()
        self.employees.register.return_value = EMPLOYEE
        response = self.client.post(reverse('employee_new'), self.form)
        self.assertRedirects(response, reverse('employee_new'), fetch_redirect_response=False)
        new = self.employees.register.call_args.args[1]
        self.assertEqual((new.login, new.warehouse_id, new.role_id), ('sidorov', 1, 6))

    def test_form_error_keeps_input(self):
        self.sign_in()
        page = self.client.post(reverse('employee_new'), {**self.form, 'password': ''})
        self.assertContains(page, 'Обязательное поле')
        self.assertContains(page, 'value="sidorov"')
        self.assertNotContains(page, 'Повтор пароля')
        self.employees.register.assert_not_called()

    def test_service_error_is_shown_over_form(self):
        self.sign_in()
        self.employees.register.side_effect = ValidationError('Логин «sidorov» уже занят')
        self.assertContains(self.client.post(reverse('employee_new'), self.form), 'Логин «sidorov» уже занят')

    def test_not_admin_gets_403(self):
        self.sign_in((PermissionName.SHIPMENT_CREATE,))
        self.employees.list_warehouses.side_effect = AccessDeniedError('Недостаточно прав для этого действия')
        self.assertEqual(self.client.get(reverse('employee_new')).status_code, 403)
        self.assertNotContains(self.client.get(reverse('home')), 'Новый сотрудник')


class HomeTests(WebTestCase):
    """Задача 1: счётчики и плитки по правам, остатки."""

    def home(self, permissions):
        self.sign_in(permissions)
        return self.client.get(reverse('home'))

    def titles(self, response, key) -> list[str]:
        return [c['title'] for c in response.context[key]]

    def test_each_role_sees_its_counters_and_tiles(self):
        cases = {
            SENIOR: (['Черновики', 'Ждут отправки', 'Едет к вам', 'Расхождения'],
                     ['Создать перевозку', 'Посмотреть перевозки'], ['Приёмка', 'Остатки']),
            KEEPER: (['Ждут отправки', 'Едет к вам'], ['Посмотреть перевозки'], ['Приёмка', 'Остатки']),
            MANAGER: (['Черновики', 'Ждут отправки', 'Расхождения'], ['Все перевозки'], []),
            DRIVER: (['Предстоящие рейсы'], ['Мои рейсы'], []),
            ADMIN: (['Черновики', 'Ждут отправки', 'Едет к вам', 'Расхождения'],
                    ['Создать перевозку', 'Все перевозки'], ['Приёмка', 'Остатки', 'Журнал операций']),
        }
        for perms, (counters, main, extra) in cases.items():
            with self.subTest(perms=perms):
                page = self.home(perms)
                self.assertEqual(self.titles(page, 'counters'), counters)
                self.assertEqual(self.titles(page, 'main_tiles'), main)
                self.assertEqual(self.titles(page, 'extra_tiles'), extra)

    def test_counters_match_list_rows(self):
        self.routes.list_routes.return_value = [
            stage(1, 100, status=StatusName.DRAFT),
            stage(2, 101, status=StatusName.DRAFT),
            stage(3, 102, status=StatusName.RESERVED),
            stage(4, 103, status=StatusName.DISCREPANCY),
        ]
        page = self.home(SENIOR)
        for counter in page.context['counters']:
            if counter['url'].startswith(reverse('shipments')):
                with self.subTest(counter=counter['title']):
                    listed = self.client.get(counter['url'])
                    self.assertEqual(len(listed.context['rows']), counter['number'])

    def test_incoming_counter_uses_receipt_service(self):
        self.receipt.get_incoming.return_value = [stage(status=StatusName.SHIPPED)] * 3
        self.assertEqual(self.home(KEEPER).context['counters'][1]['number'], 3)

    def test_stock_table_and_search(self):
        self.stock.list_stock.return_value = [
            StockItemDTO(1, 1, 'ART-001', 'Цемент М500', 'т', Decimal('48.5'), Decimal('48.5')),
            StockItemDTO(1, 2, 'ART-002', 'Болт М12', 'шт', Decimal('3200'), Decimal('400')),
        ]
        self.sign_in(KEEPER)
        page = self.client.get(reverse('stock'), {'q': 'цемент'})
        self.assertEqual([r.article_number for r in page.context['rows']], ['ART-001'])
        self.assertContains(page, 'zero')
        self.assertContains(self.client.get(reverse('stock'), {'q': 'нет такого'}), 'Ничего не найдено')

    def test_driver_and_manager_get_403_on_stock(self):
        self.stock.list_stock.side_effect = AccessDeniedError('Остатки видят только сотрудники склада')
        for perms in (DRIVER, MANAGER):
            with self.subTest(perms=perms):
                self.sign_in(perms)
                self.assertEqual(self.client.get(reverse('stock')).status_code, 403)


class ShipmentListTests(WebTestCase):
    """Задача 2: фильтры, теги, кнопки статуса."""

    stages = [
        stage(1, 100, status=StatusName.DRAFT, driver_id=3, driver_name='Петров Сергей'),
        stage(2, 101, status=StatusName.SHIPPED, driver_id=3, driver_name='Петров Сергей'),
        stage(3, 102, status=StatusName.SHIPPED, creator_id=8, creator_name='Кузнецова Мария'),
        stage(4, 103, status=StatusName.RESERVED, from_wh=SOUTH, to_wh=WAREHOUSE),
    ]

    def filtered(self, query: str) -> list[int]:
        request = RequestFactory().get(f'/shipments/?{query}')
        return [s.id for s in apply_filters(self.stages, parse_filters(request))]

    def test_same_params_or_different_params_and(self):
        self.assertEqual(self.filtered('status=draft&status=shipped&driver=3'), [1, 2])
        self.assertEqual(self.filtered('driver=none'), [3, 4])
        self.assertEqual(self.filtered('creator=8'), [3])
        self.assertEqual(self.filtered('id=101&id=103'), [2, 4])
        self.assertEqual(self.filtered('q=кузнецова'), [3])
        self.assertEqual(self.filtered('q=№102'), [3])

    def test_unknown_values_are_skipped(self):
        self.assertEqual(self.filtered('status=waiting&id=abc&driver=x'), [1, 2, 3, 4])

    def test_page_shows_rows_tokens_and_chips(self):
        self.routes.list_routes.return_value = self.stages
        self.sign_in(SENIOR)
        page = self.client.get(reverse('shipments'), {'status': 'shipped', 'driver': '3'})
        self.assertContains(page, 'Найдено: 1')
        self.assertContains(page, 'Водитель:</span>Петров С.')
        draft_chip = next(c for c in page.context['chips'] if c['label'] == 'Черновик')
        self.assertIn('driver=3', draft_chip['url'])
        self.assertIn('status=draft', draft_chip['url'])
        self.assertNotIn('status=shipped', draft_chip['url'])
        self.assertContains(self.client.get(reverse('shipments')), '· входящая', count=1)

    def test_empty_result_offers_reset(self):
        self.sign_in(SENIOR)
        page = self.client.get(reverse('shipments'), {'status': 'draft'})
        self.assertContains(page, 'Ничего не найдено.')
        self.assertContains(page, 'Сбросить фильтры')

    def test_titles_by_permissions(self):
        for perms, title in ((SENIOR, 'Перевозки'), (MANAGER, 'Все перевозки'), (DRIVER, 'Мои рейсы')):
            with self.subTest(perms=perms):
                self.sign_in(perms)
                page = self.client.get(reverse('shipments'))
                self.assertEqual(page.context['title'], title)
        self.assertNotContains(page, 'search-input')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DraftTests(WebTestCase):
    """Задача 3: форма создания и кнопки панели черновика."""

    def tearDown(self):
        shutil.rmtree(self.settings_media_root(), ignore_errors=True)

    def settings_media_root(self):
        from django.conf import settings
        return settings.MEDIA_ROOT

    def media_files(self) -> list[str]:
        import os
        root = self.settings_media_root()
        return [f for _, _, files in os.walk(root) for f in files]

    form = {
        'route': ['1', '2', '2'], 'planned_date': '2026-10-01', 'driver_id': '',
        'product_id': ['1', ''], 'quantity': ['10,5', ''],
    }

    def test_creates_draft_and_redirects_to_card(self):
        self.sign_in(SENIOR)
        self.draft.create_draft.return_value = shipment(stage())
        response = self.client.post(reverse('draft_new'), {
            **self.form, 'route': ['1', '2', '3'],
            'documents': SimpleUploadedFile('ТОРГ-12.pdf', b'%PDF', content_type='application/pdf'),
        })
        self.assertRedirects(response, reverse('shipment_detail', args=[100]), fetch_redirect_response=False)
        args = self.draft.create_draft.call_args
        self.assertEqual(args.args[2], [1, 2, 3])
        self.assertEqual([(i.product_id, i.quantity) for i in args.args[3]], [(1, '10.5')])
        self.assertEqual(len(args.kwargs['documents']), 1)
        self.assertEqual(self.messages(response), ['Черновик №100 создан'])

    def test_service_error_keeps_input_and_removes_saved_files(self):
        self.sign_in(SENIOR)
        self.draft.create_draft.side_effect = ValidationError('Соседние склады маршрута не должны совпадать')
        page = self.client.post(reverse('draft_new'), {
            **self.form,
            'documents': SimpleUploadedFile('ТОРГ-12.pdf', b'%PDF', content_type='application/pdf'),
        })
        self.assertContains(page, 'Соседние склады маршрута не должны совпадать')
        self.assertContains(page, 'value="10,5"')
        self.assertContains(page, 'Выберите файлы заново')
        self.assertEqual(page.context['form']['route'], ['2', '2'])
        self.assertEqual(self.media_files(), [])

    def test_bad_date_is_explained(self):
        self.sign_in(SENIOR)
        page = self.client.post(reverse('draft_new'), {**self.form, 'planned_date': ''})
        self.assertContains(page, 'Укажите плановую дату')
        self.draft.create_draft.assert_not_called()

    def test_without_create_permission_form_is_403(self):
        self.draft.list_warehouses.side_effect = AccessDeniedError('Недостаточно прав для этого действия')
        for perms in (KEEPER, MANAGER):
            with self.subTest(perms=perms):
                self.sign_in(perms)
                self.assertEqual(self.client.get(reverse('draft_new')).status_code, 403)

    def test_panel_buttons(self):
        self.sign_in(SENIOR)
        back = {'next': '/shipments/100/'}
        response = self.client.post(reverse('draft_add_item', args=[1]), {**back, 'product_id': '2', 'quantity': '1 000'})
        self.assertRedirects(response, '/shipments/100/', fetch_redirect_response=False)
        self.draft.add_item.assert_called_with(EMPLOYEE.id, 1, 2, '1000')
        self.client.post(reverse('draft_driver', args=[1]), {**back, 'driver_id': ''})
        self.draft.assign_driver.assert_called_with(EMPLOYEE.id, 1, None)
        self.client.post(reverse('draft_remove_item', args=[9]), back)
        self.draft.remove_item.assert_called_with(EMPLOYEE.id, 9)

    def test_attach_failure_removes_file(self):
        self.sign_in(SENIOR)
        self.draft.attach_document.side_effect = ValidationError('Этап не черновик')
        response = self.client.post(reverse('draft_attach', args=[1]), {
            'next': '/shipments/100/',
            'documents': SimpleUploadedFile('a.pdf', b'%PDF', content_type='application/pdf'),
        })
        self.assertEqual(self.messages(response), ['Этап не черновик'])
        self.assertEqual(self.media_files(), [])

    def test_detach_deletes_file_from_returned_document(self):
        self.sign_in(SENIOR)
        with mock.patch('web.views.draft.delete_stage_file') as delete:
            self.draft.remove_document.return_value = document(path='stage_documents/real.pdf')
            self.client.post(reverse('draft_detach', args=[5]), {'storage_path': 'stage_documents/forged.pdf'})
        delete.assert_called_once_with('stage_documents/real.pdf')

    def test_delete_draft_removes_files(self):
        self.sign_in(SENIOR)
        self.routes.get_shipment_progress.return_value = shipment(stage())
        self.routes.list_documents.return_value = [document(path='stage_documents/a.pdf')]
        with mock.patch('web.views.draft.delete_stage_file') as delete:
            response = self.client.post(reverse('draft_delete', args=[100]))
        self.assertRedirects(response, reverse('shipments'), fetch_redirect_response=False)
        self.draft.delete_draft.assert_called_with(EMPLOYEE.id, 100)
        delete.assert_called_once_with('stage_documents/a.pdf')


class DetailTests(WebTestCase):
    """Задача 4: кнопки карточки по правам и документы."""

    def card(self, perms, *stages, status=StatusName.DRAFT, documents=()):
        self.routes.get_shipment_progress.return_value = shipment(*stages, status=status)
        self.routes.list_documents.return_value = list(documents)
        self.sign_in(perms)
        return self.client.get(reverse('shipment_detail', args=[100]))

    def test_reserve_disabled_without_documents(self):
        page = self.card(KEEPER, stage(items=[item()]))
        self.assertContains(page, 'Нужен документ: его прикрепляет старший кладовщик')
        self.assertContains(page, 'disabled>Зарезервировать')

    def test_roles_see_their_buttons(self):
        reserved = stage(status=StatusName.RESERVED, items=[item()])
        keeper = self.card(KEEPER, reserved, status=StatusName.RESERVED, documents=[document()])
        self.assertContains(keeper, '>Отправить<')
        self.assertNotContains(keeper, 'Отменить перевозку')
        manager = self.card(MANAGER, reserved, status=StatusName.RESERVED, documents=[document()])
        self.assertContains(manager, 'Отменить перевозку')
        self.assertNotContains(manager, '>Отправить<')
        driver = self.card(DRIVER, reserved, status=StatusName.RESERVED, documents=[document()])
        for button in ('>Отправить<', 'Зарезервировать', 'Отменить перевозку', 'Удалить черновик'):
            self.assertNotContains(driver, button)

    def test_senior_gets_draft_panel(self):
        page = self.card(SENIOR, stage(items=[item()]))
        self.assertContains(page, 'Добавить товар')
        self.assertContains(page, 'Документов нет. Без документа этап не зарезервировать.')
        self.assertContains(page, 'Удалить черновик')

    def test_waiting_stage_has_no_documents_request(self):
        page = self.card(SENIOR, stage(), stage(2, order=2, status=StatusName.WAITING, from_wh=SOUTH, to_wh=WAREHOUSE))
        self.assertContains(page, 'Товары заполнятся автоматически после приёмки этапа 1')
        self.routes.list_documents.assert_called_once()

    def test_foreign_shipment_is_403_and_missing_is_404(self):
        self.sign_in(KEEPER)
        self.routes.get_shipment_progress.side_effect = AccessDeniedError('Нет прав на просмотр этой перевозки')
        self.assertEqual(self.client.get(reverse('shipment_detail', args=[100])).status_code, 403)

    def test_cancel_error_is_shown_as_message(self):
        self.sign_in(MANAGER)
        self.dispatch.cancel_shipment.side_effect = ValidationError(
            'Перевозка в статусе «Отправлено»: отменить можно, пока груз не отправлен'
        )
        response = self.client.post(reverse('shipment_cancel', args=[100]), {'next': '/shipments/100/'})
        self.assertRedirects(response, '/shipments/100/', fetch_redirect_response=False)
        self.assertIn('пока груз не отправлен', self.messages(response)[0])

    def test_reserve_message_names_warehouse(self):
        self.sign_in(KEEPER)
        self.dispatch.reserve_stage.return_value = stage(status=StatusName.RESERVED)
        response = self.client.post(reverse('stage_reserve', args=[1]))
        self.assertEqual(self.messages(response), ['Этап зарезервирован: товар в резерве склада «Склад Север»'])

    def test_document_missing_on_disk_is_404(self):
        self.sign_in(KEEPER)
        self.routes.list_documents.return_value = [document(path='stage_documents/missing.pdf')]
        self.assertEqual(self.client.get(reverse('document_open', args=[1, 5])).status_code, 404)
        self.assertEqual(self.client.get(reverse('document_open', args=[1, 6])).status_code, 404)


class ReceiptTests(WebTestCase):
    """Задача 4: ввод факта и приёмка."""

    def test_nothing_incoming(self):
        self.sign_in(KEEPER)
        self.assertContains(self.client.get(reverse('receipt')), 'На ваш склад ничего не едет')

    def test_accept_disabled_until_all_facts_saved(self):
        self.receipt.get_incoming.return_value = [
            stage(status=StatusName.SHIPPED, items=[item(1, actual='10'), item(2, name='Болт')])
        ]
        self.sign_in(KEEPER)
        page = self.client.get(reverse('receipt'))
        self.assertContains(page, 'Заполните и сохраните факт по всем позициям')
        self.assertContains(page, 'disabled>Принять этап')

    def test_error_in_one_item_does_not_stop_others(self):
        self.receipt.get_incoming.return_value = [
            stage(status=StatusName.SHIPPED, items=[item(1), item(2, name='Болт')])
        ]
        self.receipt.enter_actual_quantity.side_effect = [
            ValidationError('Факт расходится с документом — заполните комментарий'), None,
        ]
        self.sign_in(KEEPER)
        response = self.client.post(reverse('receipt_facts', args=[1]), {
            'fact_1': '9', 'comment_1': '', 'fact_2': '10,000', 'comment_2': '',
        })
        self.assertEqual(self.messages(response), [
            'Цемент М500: Факт расходится с документом — заполните комментарий',
            'Факт сохранён по 1 позиции',
        ])
        self.receipt.enter_actual_quantity.assert_called_with(EMPLOYEE.id, 2, '10.000', '')

    def test_accept_message_by_status(self):
        self.sign_in(KEEPER)
        self.receipt.accept_stage.return_value = stage(status=StatusName.DISCREPANCY)
        response = self.client.post(reverse('receipt_accept', args=[1]))
        self.assertRedirects(response, reverse('receipt'), fetch_redirect_response=False)
        self.assertEqual(self.messages(response), ['Этап принят с расхождениями'])


class OperationsTests(WebTestCase):
    """Журнал операций и выгрузка в Excel."""

    operation = OperationHistoryDTO(
        id=1, employee_id=7, employee_name='Петров Иван', operation_type=OperationType.STAGE_RESERVE,
        entity_name='ShipmentStage', entity_id=3, details={'quantity': '10.500'}, created_at=NOW,
    )

    def test_admin_sees_journal_with_filters(self):
        self.history.list_operations.return_value = [self.operation]
        self.history.list_filters.return_value = {'operation_types': ['stage.reserve'], 'entity_names': ['ShipmentStage']}
        self.sign_in(ADMIN)
        page = self.client.get(reverse('operations'), {'employee_id': '7', 'since': '2026-09-25T10:00'})
        self.assertContains(page, 'Резерв')
        self.assertContains(page, '10.500')
        kwargs = self.history.list_operations.call_args.kwargs
        self.assertEqual(kwargs['actor_employee_id'], 7)
        self.assertIsNotNone(kwargs['since'].tzinfo)

    def test_not_admin_gets_403(self):
        self.history.list_operations.side_effect = AccessDeniedError('Недостаточно прав для этого действия')
        self.history.list_filters.side_effect = AccessDeniedError('Недостаточно прав для этого действия')
        self.sign_in(SENIOR)
        self.assertEqual(self.client.get(reverse('operations')).status_code, 403)

    def test_export_is_xlsx(self):
        self.history.list_operations.return_value = [self.operation]
        self.sign_in(ADMIN)
        response = self.client.get(reverse('operations_export'))
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertTrue(response.content.startswith(b'PK'))


class ControllerLoggingTests(WebTestCase):
    def test_passwords_never_reach_log(self):
        request = RequestFactory().post('/login/', {'login': 'petrov', 'password': 'secret', 'password_repeat': 'secret'})
        self.assertEqual(request_data(request), {'login': 'petrov', 'password': '***', 'password_repeat': '***'})

    def test_business_error_is_logged_as_warning(self):
        self.sign_in(KEEPER)
        self.dispatch.ship_stage.side_effect = ValidationError('В этапе нет ни одной позиции')
        with self.assertLogs('web.controllers', level='WARNING') as logs:
            self.client.post(reverse('stage_ship', args=[1]))
        self.assertIn('В этапе нет ни одной позиции', logs.output[0])


class TagTests(TestCase):
    def test_tags(self):
        from django.template import Context, Template

        html = Template(
            "{% load warehouse_tags %}{% status_pill s %}|{{ q|qty:'т' }}|{{ n|qty:'шт' }}|{{ l|qty:'л' }}|{{ name|short_name }}"
        ).render(Context({'s': 'Черновик (Draft)', 'q': '1234.5', 'n': 12, 'l': '1.5', 'name': 'Петров Сергей'}))
        self.assertEqual(html, '<span class="pill st-draft">Черновик</span>|1\xa0234,500 т|12 шт|1,500 л|Петров С.')
