from django.urls import reverse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from warehouse.common import PermissionName, StatusName

from ..auth import employee_required
from ..controller_logging import logged
from ..errors import business_errors_as_http
from ..services import receipt_service, route_service, stock_service

CREATE = PermissionName.SHIPMENT_CREATE
DISPATCH = PermissionName.SHIPMENT_DISPATCH
ACCEPT = PermissionName.SHIPMENT_ACCEPT
VIEW_ALL = PermissionName.SHIPMENT_VIEW_ALL
WAREHOUSE_PERMISSIONS = frozenset({CREATE, DISPATCH, ACCEPT})
SHIPMENT_PERMISSIONS = WAREHOUSE_PERMISSIONS | {VIEW_ALL}


def _counter(title: str, hint: str, status: StatusName, number: int, url: str) -> dict:
    """Плашка блока «Требует внимания»."""
    return {'title': title, 'hint': hint, 'status': status, 'number': number, 'url': url}


def _tile(title: str, hint: str, url: str) -> dict:
    """Плитка блока «Действия»."""
    return {'title': title, 'hint': hint, 'url': url}


def home_counters(request, stages) -> list[dict]:
    """Счётчики по правам сотрудника; ссылки ведут на фильтры списка перевозок."""
    perms = request.actor.permissions
    shipments = reverse('shipments')
    by_status = {status: sum(1 for s in stages if s.status_name == status) for status in StatusName}
    counters = []
    if perms & {CREATE, VIEW_ALL}:
        counters.append(_counter('Черновики', 'Ещё не зарезервированы', StatusName.DRAFT,
                                 by_status[StatusName.DRAFT], f'{shipments}?status=draft'))
    if perms & {DISPATCH, VIEW_ALL}:
        counters.append(_counter('Ждут отправки', 'Товар в резерве', StatusName.RESERVED,
                                 by_status[StatusName.RESERVED], f'{shipments}?status=reserved'))
    if ACCEPT in perms:
        incoming = len(receipt_service().get_incoming(request.actor.employee_id))
        counters.append(_counter('Едет к вам', f'Отправлено на {request.session.get("warehouse_title", "ваш склад")}',
                                 StatusName.SHIPPED, incoming, reverse('receipt')))
    if perms & {CREATE, VIEW_ALL}:
        counters.append(_counter('Расхождения', 'Факт не совпал с документом', StatusName.DISCREPANCY,
                                 by_status[StatusName.DISCREPANCY], f'{shipments}?status=discrepancy'))
    if not perms & SHIPMENT_PERMISSIONS:
        counters.append(_counter('Предстоящие рейсы', 'Зарезервированы, ждут отправки', StatusName.RESERVED,
                                 by_status[StatusName.RESERVED], f'{shipments}?status=reserved'))
    return counters


def home_tiles(request) -> tuple[list[dict], list[dict]]:
    """Крупные и дополнительные плитки: показываем только доступные сотруднику."""
    perms = request.actor.permissions
    main, extra = [], []
    if CREATE in perms:
        main.append(_tile('Создать перевозку', 'Маршрут, товары, водитель, документы', reverse('draft_new')))
    if perms & SHIPMENT_PERMISSIONS:
        title = 'Все перевозки' if VIEW_ALL in perms else 'Посмотреть перевозки'
        main.append(_tile(title, 'Исходящие и входящие этапы склада', reverse('shipments')))
    else:
        main.append(_tile('Мои рейсы', 'Этапы, где вы водитель', reverse('shipments')))
    if ACCEPT in perms:
        extra.append(_tile('Приёмка', 'Ввод факта и приёмка этапов', reverse('receipt')))
    if perms & WAREHOUSE_PERMISSIONS:
        extra.append(_tile('Остатки', 'На складе, в резерве, доступно', reverse('stock')))
    if PermissionName.EMPLOYEE_MANAGE in perms:
        extra.append(_tile('Журнал операций', 'Кто, что и когда сделал', reverse('operations')))
    return main, extra


@require_GET
@employee_required
@business_errors_as_http
@logged
def home_view(request):
    """Главная: что требует внимания и куда перейти."""
    stages = route_service().list_routes(request.actor.employee_id, only_active=False)
    main, extra = home_tiles(request)
    return render(request, 'web/home/home.html', {
        'counters': home_counters(request, stages),
        'main_tiles': main,
        'extra_tiles': extra,
    })


@require_GET
@employee_required
@business_errors_as_http
@logged
def stock_view(request):
    """Остатки склада сотрудника (у администратора — всех складов) с поиском."""
    query = request.GET.get('q', '').strip()
    is_admin = PermissionName.EMPLOYEE_MANAGE in request.actor.permissions
    rows = stock_service().list_stock(request.actor.employee_id)
    if query:
        needle = query.casefold()
        rows = [
            r for r in rows
            if needle in r.article_number.casefold()
            or needle in r.product_name.casefold()
            or (is_admin and needle in r.warehouse_title.casefold())
        ]
    return render(request, 'web/home/stock.html', {'rows': rows, 'q': query, 'is_admin': is_admin})
