"""
ShipmentServiceABC — абстрактный интерфейс сервиса перевозок.
Содержит только сигнатуры методов и docstring-контракты.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Optional

from warehouse.api.dto.employee import EmployeeDTO
from warehouse.api.dto.product import ProductDTO
from warehouse.api.dto.shipment import ShipmentDTO, StageDTO, StageItemDTO
from warehouse.api.dto.warehouse import StockItemDTO
from warehouse.api.dto.warehouse import WarehouseDTO


class ShipmentServiceABC(ABC):
    """Абстрактный интерфейс сервиса управления перевозками."""

    @abstractmethod
    def get_available_stock(self, employee_id: int) -> list[StockItemDTO]:
        """Свободные остатки склада сотрудника (stock.list_available).
        Склад берётся из профиля сотрудника, а не из параметра."""

    @abstractmethod
    def get_my_shipments(self, employee_id: int) -> list[ShipmentDTO]:
        """Перевозки, созданные этим сотрудником (shipments.list_by_creator)."""

    @abstractmethod
    def create_draft(
        self,
        employee_id: int,
        route: list[int],
        planned_date: date,
    ) -> int:
        """Создаёт перевозку «Черновик (Draft)».
        Маршрут — список складов, например [1, 2, 3].
        Проверки: не меньше 2 складов; первый склад — склад сотрудника;
        склады не повторяются; все склады существуют; дата не в прошлом.
        Этап 1 получает «Черновик», остальные — «В ожидании».
        Возвращает shipment_id."""

    @abstractmethod
    def add_item(
        self,
        employee_id: int,
        shipment_id: int,
        product_id: int,
        quantity: Decimal,
    ) -> int:
        """Добавляет товар в этап 1 перевозки.
        Проверки: перевозка — черновик; склад этапа 1 — склад сотрудника;
        количество > 0, не больше 3 знаков после запятой; товар существует;
        свободного остатка хватает.
        Если товар уже есть в этапе — увеличивает количество, иначе добавляет новую строку.
        Возвращает item_id."""

    @abstractmethod
    def update_item_quantity(
        self,
        employee_id: int,
        item_id: int,
        quantity: Decimal,
    ) -> None:
        """Обновляет количество в строке документа.
        Те же проверки, что и add_item. Сохранение через set_document_quantity."""

    @abstractmethod
    def remove_item(self, employee_id: int, item_id: int) -> None:
        """Удаляет строку из черновика.
        Только в черновике и только на своём складе (stage_items.delete)."""

    @abstractmethod
    def assign_driver(
        self,
        employee_id: int,
        stage_id: int,
        driver_id: Optional[int],
    ) -> None:
        """Назначает водителя на этап.
        Этап уходит со склада сотрудника и ещё не отправлен (stages.assign_driver)."""

    @abstractmethod
    def delete_draft(self, employee_id: int, shipment_id: int) -> None:
        """Удаляет черновик перевозки.
        Только черновик и только создатель (shipments.delete)."""

    @abstractmethod
    def ship_stage(self, employee_id: int, stage_id: int) -> None:
        """Отправляет этап.
        Проверки: этап в статусе «Черновик» или «Зарезервировано»;
        уходит со склада сотрудника; в нём есть товары.
        Блокирует строки остатков: stock.get_many(..., for_update=True).
        Этап «Черновик»: проверяет свободный остаток, уменьшает quantity.
        Этап «Зарезервировано»: проверяет резерв, уменьшает quantity и reserved.
        Этап и перевозка получают «Отправлено», у этапа записывается sent_at."""
