import logging
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.orm import configure_mappers
from dependency_injector.wiring import Provide, inject

from container import Container
from warehouse.common import RoleName
from warehouse.dal.unit_of_work import UnitOfWork
from warehouse.common.logger import setup_logging
from warehouse.common.exceptions import BusinessError  

# Избавляемся от лишнего кода FastAPI, если Django выступает фронтендом.
# Оставляем только CLI-скрипт проверки работоспособности (Smoke Test)

def check(name: str, func) -> bool:
    try:
        result = func()
    except Exception as e:  # noqa: BLE001
        logging.error(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        return False
    logging.info(f"  [ OK ] {name}: {result}")
    return True


@inject
def main(uow: UnitOfWork = Provide[Container.uow]) -> None:
    logging.info(f"UoW из контейнера: {type(uow).__name__}")
    
    # Сборка мапперов SQLAlchemy 2.0
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
    # Инициализируем логи строго ОДИН раз
    setup_logging()
    
    container = Container()
    # ФИКС ИНЖЕКЦИИ: Явно указываем имя модуля "__main__", чтобы wiring_config сработал в CLI
    container.wire(modules=["__main__"])
    
    logging.info("Запуск скрипта верификации слоев системы...")
    main()
