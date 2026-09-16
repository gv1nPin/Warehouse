"""Проверка, что проект собирается: контейнер отдаёт UoW, модели сходятся, БД отвечает.

Запуск из папки src:  python main.py
Проверка только читает данные и ничего не меняет в БД.
"""

from dependency_injector.wiring import Provide, inject
from sqlalchemy import text
from sqlalchemy.orm import configure_mappers

from container import Container
from Warehouse.Common import RoleName
from Warehouse.DAL.unit_of_work import UnitOfWork


def check(name: str, func) -> bool:
    try:
        result = func()
    except Exception as e:  # noqa: BLE001 — проверка должна пройти по всем пунктам
        print(f"  [FAIL] {name}: {type(e).__name__}: {e}")
        return False
    print(f"  [ OK ] {name}: {result}")
    return True


@inject
def main(uow: UnitOfWork = Provide[Container.uow]) -> None:
    print(f"UoW из контейнера: {type(uow).__name__}")
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

    print("Всё работает." if all(results) else "Есть ошибки, см. выше.")


if __name__ == "__main__":
    container = Container()
    # При запуске `python main.py` модуль называется __main__, а не main — связываем явно.
    container.wire(modules=[__name__])
    main()
