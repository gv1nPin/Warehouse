# Warehouse

Система межскладских перевозок: черновик → резерв → отправка → транзит → приёмка (в том числе с расхождениями), с ролями, остатками и журналом операций.

## Что умеет система

- Многоэтапный маршрут `склад A → … → склад N`
- Черновик: товары, водитель, сопроводительные документы
- Резерв свободного остатка и отправка этапа
- Автоматический транзит: после приёмки товар резервируется на следующем складе
- Приёмка с фактом; при расхождении обязателен комментарий
- Остатки: `quantity` / `reserved_quantity`
- Роли и права на уровне склада (админ видит всё)
- JWT-вход, журнал действий, выгрузка в Excel
- HTML-интерфейс + небольшой JSON API

## Архитектура

Django **не** хранит складские данные. Он только HTTP, шаблоны и сессия. Домен живёт в `src/warehouse`.

```
web (Django)
    │  views / templates / JWT в session
    ▼
BLL  сервисы + abstract interfaces
    │  транзакцию сервис открывает сам
    ▼
DAL  SQLAlchemy 2 + Unit of Work + PostgreSQL
```

| Слой | Путь | Ответственность |
|------|------|-----------------|
| Presentation | `web/` | маршруты, формы, HTMX-подобные POST, загрузка файлов |
| BLL | `src/warehouse/bll/` | правила статусов, прав, остатков |
| Common | `src/warehouse/common/` | DTO, мапперы, константы, исключения, JWT/bcrypt, лог |
| DAL | `src/warehouse/dal/` | entities, repositories, `UnitOfWork` |
| IoC | `src/container.py` | `dependency-injector` |
| Schema | `sql_fullset.txt` | PostgreSQL DDL |

SQLite (`db.sqlite3`) — только сессии Django. Склад — PostgreSQL.

## Стек

| Компонент | Версия / пакет |
|-----------|----------------|
| Python | 3.12 (в репозитории есть `.pyc` под 3.12) |
| Web | Django 6.1.1 |
| ORM | SQLAlchemy 2.0.52 |
| БД | PostgreSQL + `psycopg2-binary` |
| Auth | PyJWT 2.10.1, bcrypt 4.2.1 |
| DI | dependency-injector 4.45.0 |
| Конфиг | python-dotenv |
| Excel | openpyxl 3.1.5 |
| Лицензия | MIT, © 2026 Hew_Maan |

## Быстрый старт

### Требования

- Python 3.12+
- PostgreSQL

### Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Конфигурация

`python manage.py …` сам копирует `.env.example` → `.env`, если файла нет. Потом обязательно смените секреты:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=Warehouse
DB_USER=postgres
DB_PASSWORD=

DEBUG=1
SECRET_KEY=замените
ALLOWED_HOSTS=localhost,127.0.0.1

JWT_SECRET=замените
JWT_EXPIRE_MINUTES=480
```

Без `SECRET_KEY` / `JWT_SECRET` в `DEBUG=1` Django подставит временные ключи; в проде это ошибка конфигурации.

### База

```bash
createdb Warehouse
psql -U postgres -d Warehouse -f sql_fullset.txt
```

Строки справочников **должны совпадать** с `src/warehouse/common/constants.py` символ в символ, включая английскую часть в скобках:

- роли: `Старший кладовщик`, `Кладовщик`, `Менеджер`, `Водитель`, `Администратор системы`
- статусы: `Черновик (Draft)`, `Зарезервировано (Reserved)`, …
- права: `shipment:create`, `shipment:dispatch`, `shipment:accept`, `shipment:cancel`, `shipment:view_all`, `employee:manage`

### Запуск

```bash
python manage.py runserver
```

Откройте `http://127.0.0.1:8000/`. Логи пишутся в `logs/warehouse.log`.

## Жизненный цикл перевозки

```
create_draft
    этап 1: Черновик
    этапы 2..N: В ожидании
        │  товары, водитель, ≥1 документ
        ▼
reserve_stage          → Зарезервировано  (свободный остаток → резерв)
        │
        ├─ cancel_shipment  (до отправки) → Отменено, резерв возвращается
        ▼
ship_stage             → Отправлено       (списание quantity + reserved)
        ▼
enter_actual_quantity  (факт; при расхождении — комментарий)
        ▼
accept_stage
    совпало      → Принято
    разошлось    → Принято с расхождениями
        ▼
transit.after_stage_accepted
    есть следующий этап → количества копируются, резерв на транзитном складе,
                          этап → Зарезервировано
    последнего нет      → перевозка закрывается
```

Правила черновика:

- первый склад маршрута — склад сотрудника-создателя;
- без документа этап не резервируется;
- править товары/документы можно только у этапа «Черновик»;
- водителя можно назначить до отправки.

## Роли и права

| Роль | create | dispatch | accept | cancel | view_all | employee:manage |
|------|:------:|:--------:|:------:|:------:|:--------:|:---------------:|
| Старший кладовщик | ✓ | ✓ | ✓ | | | |
| Кладовщик | | ✓ | ✓ | | | |
| Менеджер | | | | ✓ | ✓ | |
| Водитель | только свои рейсы | | | | | |
| Администратор системы | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Админ не привязан к одному складу. Остальные видят «свой» склад; обращение к чужому → `AccessDeniedError` (403).

Проверка прав — `AccessService` + декораторы `employee_required` / `api_employee_required`. Токен JWT лежит в Django-сессии (`session['token']`), не в cookie отдельно.

## Модель данных (сжато)

Справочники: `Measurements`, `Statuses`, `Permissions`, `Roles`, `RolePermissions`.

Домен:

- `Warehouses`, `Employees` (login + bcrypt hash, soft-delete)
- `Products`, `StockOnWarehouse(quantity, reserved_quantity)` с `reserved ≤ quantity`
- `Shipments` → `ShipmentStages` (порядок, from/to, driver, acceptor, sent_at/received_at)
- `StageItems(document_quantity, actual_quantity, comment)`
- `StageDocuments` — метаданные; байты файла хранит web в `media/stage_documents/`
- `operation_history` — аудит (`auth.login`, `shipment.create`, `stage.ship`, …)

Ограничения схемы: разные склады на этапе, `received_at ≥ sent_at`, каскад удаления этапов/позиций вместе с перевозкой.

## Карта кода

### BLL-сервисы

| Сервис | Задача |
|--------|--------|
| `ShipmentDraftService` | маршрут, позиции, водитель, документы, удаление черновика |
| `ShipmentDispatchService` | резерв, отправка, отмена |
| `ShipmentReceiptService` | входящие, факт, приёмка |
| `ShipmentTransitCoordinator` | внутренний шаг после accept (не из web) |
| `RouteQueryService` | списки/карточка перевозки |
| `StockQueryService` | остатки склада |
| `LoginService` / `AccessService` | JWT, актор, права |
| `EmployeeService` | регистрация / блокировка |
| `OperationHistoryService` | журнал + Excel |

Web берёт сервисы из `web/services.py` (фабрики контейнера).

### Экраны

| URL | Экран |
|-----|--------|
| `/login/` | вход |
| `/` | дашборд: счётчики «требует внимания» по правам |
| `/stock/` | остатки |
| `/shipments/` | список перевозок |
| `/shipments/new/` | новый черновик |
| `/shipments/<id>/` | карточка: резерв / отправка / отмена |
| `/receipt/` | входящие, факт, принять |
| `/operations/` | журнал, деталь, `/operations/export/` |
| `/employees/new/` | регистрация сотрудника |

JSON: `/api/auth/login/`, `/api/stock/`, `/api/shipments/draft/`, ship / accept / cancel.

### Ошибки BLL

| Класс | HTTP |
|-------|------|
| `ValidationError` | 400 |
| `AuthError` | 401 |
| `AccessDeniedError` | 403 |
| `NotFoundError` | 404 |
| `InvalidStatusError` | 409 |

Ловит `web.middleware.SQLAlchemyAndBusinessErrorMiddleware`.

## Структура репозитория

```
Warehouse/
├── config/                 Django settings, urls, wsgi/asgi
├── web/                    приложение Django
│   ├── views/              home, draft, detail, shipments, receipt, operations, auth, api
│   ├── templates/web/
│   ├── auth.py             JWT ↔ session
│   ├── middleware.py
│   └── uploads.py          документы этапов, лимит 10 МБ
├── src/
│   ├── container.py
│   ├── main.py             CLI-проверка слоёв
│   └── warehouse/
│       ├── bll/{interfaces,services}/
│       ├── dal/{entities,repositories,unit_of_work.py,database.py}
│       └── common/{dto,mappers,constants,exceptions,security,logger}
├── test/                   pytest (частично, conftest пустой)
├── documentation/          HTML-прототип UI
├── sql_fullset.txt
├── manage.py
├── requirements.txt
└── .env.example
```

`src/` добавляется в `sys.path` из `manage.py` и `config/settings.py`.

## Разработка

```bash
pytest
python -m src.main    # wiring контейнера
```

Тесты есть для employee/stock; `test/conftest.py` пока пустой — фикстуры БД нужно дописать.

Ветки в git отражают слои: `SQLAlchemyORM`, `DTO`, `Mappers`, `AuthService`, `Receipt`, `dispatch`, `Transit`, `AuditTrail`, `QueryService`.

## Ограничения текущего кода

- справочники не сидятся из Python — только SQL + ручное совпадение строк с `constants.py`
- нет Docker / CI в дереве
- часть тестов-заглушек, `__pycache__` и `db.sqlite3` попали в архив
- JWT в Django-сессии: удобно для HTML, для чистого API лучше Authorization: Bearer
- файлы документов при каскадном удалении этапа в БД web должен чистить сам

## Лицензия

MIT. См. [LICENSE.md](LICENSE.md).
