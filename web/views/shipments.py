from django.shortcuts import render
from django.views.decorators.http import require_GET

from warehouse.common import PermissionName, StatusName
from warehouse.common.dto import StageDTO

from ..auth import employee_required
from ..controller_logging import logged
from ..errors import business_errors_as_http
from ..services import route_service
from ..templatetags.warehouse_tags import short_name, status_label

STATUS_FILTERS = {
    'draft': StatusName.DRAFT,
    'reserved': StatusName.RESERVED,
    'shipped': StatusName.SHIPPED,
    'received': StatusName.RECEIVED,
    'discrepancy': StatusName.DISCREPANCY,
    'cancelled': StatusName.CANCELLED,
}
CHIPS = (
    ('', 'Все'),
    ('draft', 'Черновик'),
    ('reserved', 'Зарезервировано'),
    ('shipped', 'Отправлено'),
    ('discrepancy', 'С расхождениями'),
    ('received', 'Принято'),
    ('cancelled', 'Отменено'),
)
TAGS = {'id': 'Перевозка', 'status': 'Статус', 'driver': 'Водитель', 'creator': 'Создал', 'q': 'Текст'}
NO_DRIVER = 'none'
SHIPMENT_PERMISSIONS = frozenset({
    PermissionName.SHIPMENT_CREATE,
    PermissionName.SHIPMENT_DISPATCH,
    PermissionName.SHIPMENT_ACCEPT,
    PermissionName.SHIPMENT_VIEW_ALL,
})


def _unique(values) -> list:
    """Значения без повторов в исходном порядке."""
    return list(dict.fromkeys(values))


SKIP = object()


def _parse(param: str, raw: str):
    """Значение одного GET-параметра или SKIP, если оно неизвестно."""
    raw = raw.strip()
    if param in ('id', 'creator') or (param == 'driver' and raw != NO_DRIVER):
        return int(raw) if raw.isdigit() else SKIP
    if param == 'driver':
        return None
    if param == 'status':
        return raw if raw in STATUS_FILTERS else SKIP
    return raw or SKIP


def parse_filters(request) -> dict[str, list]:
    """Фильтры из GET-параметров; неизвестные значения пропускаются."""
    filters = {}
    for param in TAGS:
        values = [_parse(param, v) for v in request.GET.getlist(param)]
        filters[param] = _unique(v for v in values if v is not SKIP)
    return filters


def _search_text(stage: StageDTO) -> str:
    """Всё, по чему ищет свободный текст: номер, статус, водитель, создатель, склады."""
    return ' '.join((
        f'№{stage.shipment_id}',
        status_label(stage.status_name),
        stage.driver_name or 'не назначен',
        stage.creator_name,
        stage.from_warehouse.title,
        stage.to_warehouse.title,
    )).casefold()


def apply_filters(stages: list[StageDTO], filters: dict[str, list]) -> list[StageDTO]:
    """Одинаковые параметры — ИЛИ, разные — И."""
    statuses = {STATUS_FILTERS[key] for key in filters['status']}
    texts = [q.casefold().lstrip('№') for q in filters['q']]
    checks = (
        (filters['id'], lambda s: s.shipment_id in filters['id']),
        (statuses, lambda s: s.status_name in statuses),
        (filters['driver'], lambda s: s.driver_id in filters['driver']),
        (filters['creator'], lambda s: s.creator_id in filters['creator']),
        (texts, lambda s: any(t in _search_text(s) for t in texts)),
    )
    active = [match for values, match in checks if values]
    return [s for s in stages if all(match(s) for match in active)]


def _query(request, param: str, values: list[str]) -> str:
    """Адрес списка, где у param заменены значения, остальные фильтры те же."""
    params = request.GET.copy()
    params.setlist(param, values)
    return f'{request.path}?{params.urlencode()}' if params else request.path


def _without(request, param: str, value) -> str:
    """Адрес без одного значения фильтра — для ✕ у тега."""
    return _query(request, param, [v for v in request.GET.getlist(param) if _parse(param, v) != value])


def filter_tokens(request, filters: dict[str, list], stages: list[StageDTO]) -> list[dict]:
    """Теги активных фильтров для поля поиска."""
    people = {s.driver_id: s.driver_name for s in stages if s.driver_id}
    people.update({s.creator_id: s.creator_name for s in stages})
    labels = {
        'id': lambda v: f'№{v}',
        'status': lambda v: status_label(STATUS_FILTERS[v]),
        'driver': lambda v: 'не назначен' if v is None else short_name(people.get(v, f'№{v}')),
        'creator': lambda v: short_name(people.get(v, f'№{v}')),
        'q': lambda v: v,
    }
    return [
        {'tag': TAGS[param], 'label': labels[param](value), 'remove_url': _without(request, param, value)}
        for param, values in filters.items()
        for value in values
    ]


def status_chips(request, filters: dict[str, list]) -> list[dict]:
    """Кнопки статуса: меняют только status, остальные фильтры сохраняются."""
    current = filters['status']
    return [
        {
            'label': label,
            'url': _query(request, 'status', [key] if key else []),
            'pressed': current == [key] if key else not current,
        }
        for key, label in CHIPS
    ]


def suggest_data(stages: list[StageDTO]) -> dict:
    """Списки для подсказок в поле поиска: номера, статусы, водители, создатели."""
    present = {s.status_name for s in stages}
    drivers = {s.driver_id: short_name(s.driver_name) for s in stages if s.driver_id}
    if any(s.driver_id is None for s in stages):
        drivers[NO_DRIVER] = 'не назначен'
    return {
        'ids': _unique(s.shipment_id for s in stages),
        'statuses': [[key, status_label(status)] for key, status in STATUS_FILTERS.items() if status in present],
        'drivers': [{'id': str(k), 'name': v} for k, v in drivers.items()],
        'creators': [{'id': str(k), 'name': short_name(v)} for k, v in {s.creator_id: s.creator_name for s in stages}.items()],
    }


@require_GET
@employee_required
@business_errors_as_http
@logged
def shipment_list_view(request):
    """Этапы, которые видит сотрудник, с фильтрами и поиском из адреса."""
    perms = request.actor.permissions
    stages = sorted(
        route_service().list_routes(request.actor.employee_id, only_active=False),
        key=lambda s: (-s.shipment_id, s.stage_order),
    )
    filters = parse_filters(request)
    own_trips = not perms & SHIPMENT_PERMISSIONS
    if own_trips:
        title, subtitle = 'Мои рейсы', 'Этапы, где вы назначены водителем'
    elif PermissionName.SHIPMENT_VIEW_ALL in perms:
        title, subtitle = 'Все перевозки', 'Перевозки всех складов'
    else:
        title, subtitle = 'Перевозки', f'Исходящие и входящие этапы: {request.session.get("warehouse_title", "ваш склад")}'
    return render(request, 'web/shipments/list.html', {
        'title': title,
        'subtitle': subtitle,
        'own_trips': own_trips,
        'rows': apply_filters(stages, filters),
        'filtered': any(filters.values()),
        'tokens': filter_tokens(request, filters, stages),
        'chips': status_chips(request, filters),
        'hidden_params': [(k, v) for k in TAGS for v in request.GET.getlist(k)],
        'suggest_data': suggest_data(stages),
        'my_warehouse_id': request.actor.warehouse_id,
    })
