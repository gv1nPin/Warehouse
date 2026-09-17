"""Проверка, что проект собирается: контейнер отдаёт UoW, модели сходятся, БД отвечает.

Запуск из папки src:  python main.py
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dependency_injector.wiring import Provide, inject
from sqlalchemy import text
from sqlalchemy.orm import configure_mappers

from container import Container
from warehouse.common import RoleName
from warehouse.dal.unit_of_work import UnitOfWork
from warehouse.common.logger import setup_logging

from warehouse.common.exceptions import BusinessError  


def setup_exception_handlers(app: FastAPI) -> None:
    """Подключает глобальные перехватчики исключений к приложению FastAPI."""

    # 1. Перехват всех кастомных бизнес-ошибок (400, 401, 403, 404, 409)
    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):
        status_code = getattr(exc, "status_code", 500)
        
        # Логируем как WARNING (это ожидаемая ошибка логики, а не падение сервера)
        logging.warning(
            f"Бизнес-ошибка [{exc.__class__.__name__}] при запросе {request.url.path} -> {exc.message}"
        )
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.__class__.__name__,  # Вернет "NotFoundError", "AuthError" и т.д.
                "detail": exc.message            # Понятный текст ошибки
            }
        )

    # 2. Перехват критических непредвиденных падений (Unhandled Exception -> 500)
    @app.exception_handler(Exception)
    async def critical_error_handler(request: Request, exc: Exception):
        # Пишем в логгер с уровнем ERROR и полным Трейсбэком (Stack Trace) для отладки
        logging.exception(f"Критический сбой (500) на эндпоинте {request.url.path}: {exc}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "detail": "Внутренняя ошибка сервера. Инцидент зафиксирован в техлоггере."
            }
        )

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    # Данный блок выполняется СТРОГО ОДИН РАЗ при старте веб-сервера uvicorn
    setup_logging()
    logging.info("Веб-сервер FastAPI успешно запущен и готов принимать запросы.")
    yield
    # Данный блок выполнится при штатной остановке сервера (если нужно закрыть коннекты)
    logging.info("Веб-сервер FastAPI завершает свою работу.")


# Инициализация FastAPI и подключение обработчиков
app = FastAPI(lifespan=lifespan)
setup_exception_handlers(app)

def check(name: str, func) -> bool:
    try:
        result = func()
    except Exception as e:  # noqa: BLE001
        # Теперь выводим ошибки проверки через настроенный техлоггер
        logging.error(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        return False
    logging.info(f"  [ OK ] {name}: {result}")
    return True


@inject
def main(uow: UnitOfWork = Provide[Container.uow]) -> None:
    logging.info(f"UoW из контейнера: {type(uow).__name__}")
    results = [check("Связи между моделями", lambda: configure_mappers() or "без ошибок")]

    with uow:
        checks = {
            "Подключение к БД": lambda: uow.session.scalar(text("select version()")).split(",")[0],
            "Статусы": uow.statuses.list_all,
            "Роли": uow.roles.list_all,
            "Единицы измерения": uow.measurements.list_all,
            "Склады": lambda: len(uow.warehouses.list_active()),
            "Товары": lambda: len(uow.products.list_active()),
            "Старшие кладовщики": lambda: len(uow.employees.list_by_role(RoleName.SENIOR_STOREKEEPER)),
            "Остатки склада 1": lambda: len(uow.stock.list_by_warehouse(1)),
            "Все пути": lambda: len(uow.stages.list_all(with_items=True)),
            "Отгрузка 1": lambda: uow.shipments.get_by_id(1),
            "Товары этапа 1": lambda: len(uow.stage_items.list_by_stage(1)),
        }
        results += [check(name, func) for name, func in checks.items()]
        uow.rollback()

    if all(results):
        logging.info("Всё работает. Сборка проекта успешна.")
    else:
        logging.critical("Проверка завершена С ОШИБКАМИ! Проверьте логи выше.")


if __name__ == "__main__":
    # Инициализируем логи СРАЗУ, чтобы при `python main.py` вывод шел через RotatingFileHandler
    setup_logging()
    
    container = Container()
    container.wire(modules=[__name__])
    main()
