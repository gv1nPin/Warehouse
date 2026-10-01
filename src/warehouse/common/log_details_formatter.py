from datetime import date, datetime
from decimal import Decimal
from typing import Any

class LogDetailsFormatter:
    """Централизованный трансформер для словарей details в журнале операций."""

    @classmethod
    def format(cls, operation_type: str, details: dict[str, Any] | None) -> dict[str, Any] | None:
        if details is None:
            return None
        
        # Динамически ищем метод форматирования, например: DRIVER_ASSIGN -> _format_driver_assign
        method_name = f"_format_{operation_type.lower()}"
        handler = getattr(cls, method_name, cls._format_default)
        return handler(details)

    @classmethod
    def _format_employee_register(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Причесываем логи регистрации нового сотрудника/пользователя."""
        return {
            "login": str(details.get("login", "")).strip(),
            "role_id": cls._to_int_or_none(details.get("role_id")),
            "warehouse_id": cls._to_int_or_none(details.get("warehouse_id") or details.get("warehouse")),
        }

    @classmethod
    def _format_driver_assign(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Причесываем логи назначения водителя на этап."""
        return {
            "driver_id": cls._to_int_or_none(details.get("driver_id")),
            "previous_driver_id": cls._to_int_or_none(details.get("previous_driver_id")),
            "action_type": "reassigned" if details.get("previous_driver_id") else "assigned"
        }

    @classmethod
    def _format_shipment_create(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Причесываем логи создания черновика перевозки."""
        return {
            "route": [int(w_id) for w_id in details.get("route", [])],
            "planned_date": cls._to_iso_date(details.get("planned_date")),
            "total_items": len(details.get("items", [])),
            "driver_id": cls._to_int_or_none(details.get("driver_id")),
            "documents_count": len(details.get("documents", []))
        }

    @classmethod
    def _format_item_add(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Причесываем логи добавления товара в этап."""
        return {
            "product_id": cls._to_int_or_none(details.get("product_id")),
            "quantity": str(details.get("quantity")),  # Сохраняем Decimal как строку во избежание float-ошибок
            "is_replaced": bool(details.get("replaced", False))
        }

    @classmethod
    def _format_default(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Базовое причесывание для всех остальных типов логов с поддержкой вложенных списков."""
        cleaned: dict[str, Any] = {}
        for key, value in details.items():
            if isinstance(value, (Decimal, date, datetime)):
                cleaned[key] = str(value)
            elif isinstance(value, list):
                # Безопасно обрабатываем списки, если внутри лежат Decimal/Date
                cleaned[key] = [
                    str(v) if isinstance(v, (Decimal, date, datetime)) else v 
                    for v in value
                ]
            else:
                cleaned[key] = value
        return cleaned

    @classmethod
    def _format_stage_ship(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Причесываем логи фактической отправки этапа перевозки со склада."""
        raw_items = details.get("items", [])
        cleaned_items = []
        
        if isinstance(raw_items, list):
            for item in raw_items:
                cleaned_items.append({
                    "product_id": cls._to_int_or_none(item.get("product_id")),
                    "quantity": str(item.get("quantity"))
                })
                
        return {
            "shipment_id": cls._to_int_or_none(details.get("shipment_id")),
            "from_warehouse_id": cls._to_int_or_none(details.get("from_warehouse_id")),
            "to_warehouse_id": cls._to_int_or_none(details.get("to_warehouse_id")),
            "items": cleaned_items
        }

    @classmethod
    def _format_fact_enter(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Причесываем логи ввода фактического количества товара."""
        return {
            "stage_id": cls._to_int_or_none(details.get("stage_id")),
            "product_id": cls._to_int_or_none(details.get("product_id")),
            "actual_quantity": str(details.get("actual_quantity")),
            "document_quantity": str(details.get("document_quantity")),
            "comment": str(details.get("comment")) if details.get("comment") and details.get("comment") != "None" else None
        }

    #Приёмка
    @classmethod
    def _format_stage_accept(cls, details: dict[str, Any]) -> dict[str, Any]:
        """Причесываем логи окончательной приёмки этапа перевозки."""
        raw_discr = details.get("discrepancies", [])
        cleaned_discr = []
        
        if isinstance(raw_discr, list):
            for d in raw_discr:
                cleaned_discr.append({
                    "product_id": cls._to_int_or_none(d.get("product_id")),
                    "discrepancy_quantity": str(d.get("discrepancy_quantity"))
                })
                
        return {
            "shipment_id": cls._to_int_or_none(details.get("shipment_id")),
            "warehouse_id": cls._to_int_or_none(details.get("warehouse_id")),
            "status": str(details.get("status", "Received")),
            "discrepancies": cleaned_discr
        }

    # Приведения типов
    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _to_iso_date(value: Any) -> str:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return str(value)
