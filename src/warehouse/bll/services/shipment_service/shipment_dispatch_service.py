import logging
from datetime import date, datetime, timezone
from typing import List

from warehouse.bll.interfaces.shipment_service.abstract_shipment_dispatch_service import AbstractShipmentDispatchService
from warehouse.common.constants import StatusName
from warehouse.api.mappers.shipments_mappers import ShipmentMapper

# Импорт ваших кастомных классов бизнес-ошибок
from warehouse.common.security import (
    BusinessError,
    ValidationError,
    AuthError,
    AccessDeniedError,
    NotFoundError,
    InvalidStatusError
)


class ShipmentDispatchService(AbstractShipmentDispatchService):
    def __init__(self, uow):
        self.uow = uow

    def create_shipment_draft(self, employee_id: int, planned_date: date, route_warehouses: List[int]) -> int:
        logging.info(f"Сотрудник ID {employee_id} инициировал создание черновика на дату {planned_date}")
        
        # 1. Первичные проверки бизнес-логики из ТЗ
        if planned_date < date.today():
            raise ValidationError("Плановая дата не может быть в прошлом.")
        
        if len(route_warehouses) < 2:
            raise ValidationError("Маршрут должен содержать как минимум 2 склада.")
            
        # Проверка ТЗ: склады в маршруте не должны повторяться
        if len(route_warehouses) != len(set(route_warehouses)):
            raise ValidationError("Склады в маршруте не должны повторяться.")
        
        with self.uow:  
            # 2. Поиск сотрудника и проверка прав
            creator = self.uow.employee.get_by_id_with_permissions(employee_id)
            if not creator:
                raise NotFoundError("Сотрудник-создатель не найден.")
                
            # ТЗ: Склад берётся из профиля, а не из параметра
            employee_warehouse_id = creator.get("warehouse_id")
            if not employee_warehouse_id:
                raise AccessDeniedError("За сотрудником не закреплен ни один склад.")
                
            # Проверка ТЗ: первый склад в маршруте — склад сотрудника
            if route_warehouses[0] != employee_warehouse_id:
                raise AccessDeniedError("Первый склад в маршруте должен быть вашим личным складом.")
                
            # Проверка ТЗ: все указанные склады существуют в БД
            for wh_id in route_warehouses:
                if not self.uow.warehouses.get_by_id(wh_id):
                    raise NotFoundError(f"Склад с ID {wh_id} не существует в базе данных.")

            # Проверка прав доступа роли ("shipment:create")
            if "shipment:create" not in creator.get("permissions", []):
                logging.warning(f"ОТКАЗ В ДОСТУПЕ: Сотрудник ID {employee_id} пытался создать перевозку без прав!")
                
                failed_audit_data = ShipmentMapper.to_operation_history_data(
                    employee_id=employee_id,
                    operation_type="ACCESS_DENIED_CREATE_SHIPMENT",
                    entity_name="Shipment",
                    entity_id=None,
                    details={"reason": "Missing 'shipment:create' permission"}
                )
                self.uow.history.log_operation(failed_audit_data)
                raise AccessDeniedError("У вашей роли нет прав на создание перевозок.")
            
            # 3. Создание главной записи перевозки
            shipment_id = self.uow.dispatch.create_shipment(
                status_id=StatusName.DRAFT, creator_id=employee_id, planned_date=planned_date
            )
            
            # 4. Генерация этапов (ТЗ: Этап 1 получает «Черновик», остальные — «В ожидании»)
            for i in range(len(route_warehouses) - 1):
                from_wh = route_warehouses[i]
                to_wh = route_warehouses[i + 1]
                stage_order = i + 1
                initial_stage_status = StatusName.DRAFT if stage_order == 1 else StatusName.IN_WAITING 
                
                self.uow.dispatch.create_stage(
                    shipment_id=shipment_id, 
                    stage_order=stage_order,
                    from_warehouse_id=from_wh, 
                    to_warehouse_id=to_wh, 
                    status_id=initial_stage_status
                )
                
            # 5. Успешный аудит операции
            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=employee_id,
                operation_type="SHIPMENT_DRAFT_CREATED",
                entity_name="Shipment",
                entity_id=shipment_id,
                details={"planned_date": str(planned_date), "route": route_warehouses}
            )
            self.uow.history.log_operation(audit_data)
                
            logging.info(f"Успешно создан черновик Shipment ID {shipment_id} сотрудником {employee_id}")
            return shipment_id

    def add_item_to_stage(self, employee_id: int, stage_id: int, product_id: int, document_quantity: float) -> None:
        # 1. Проверки бизнес-логики из ТЗ
        if document_quantity <= 0:
            raise ValidationError("Количество товара должно быть больше нуля.")
        logging.info(f"Запуск резервирования остатков для этапа ID {stage_id} сотрудником {employee_id}")
        with self.uow:  
            # 1. Проверка существования этапа
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise NotFoundError("Этап не найден.")
                
            # Проверка прав: резервировать товары может только сотрудник этого склада
            creator = self.uow.employee.get_by_id_with_permissions(employee_id)
            if not creator or creator.get("warehouse_id") != stage["from_warehouse_id"]:
                raise AccessDeniedError("Вы можете резервировать товары только на своём складе.")
                
            # 2. Проверка ТЗ: в этапе должны быть товары
            items = self.uow.dispatch.get_stage_items(stage_id)
            if not items:
                raise ValidationError("Невозможно зарезервировать пустой этап.")
                
            # 3. Цикл блокировки резервов: увеличиваем reserved_quantity для каждой позиции
            for item in items:
                self.uow.dispatch.increase_reservation(
                    warehouse_id=stage["from_warehouse_id"], 
                    product_id=item["product_id"], 
                    amount=float(item["document_quantity"])  
                )
                
            # Меняем статус самого этапа доставки
            self.uow.dispatch.update_stage_status(stage_id, status_id=StatusName.RESERVED)
            
            # 4. Аудит операции
            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=employee_id,
                operation_type="STAGE_ITEMS_RESERVED",
                entity_name="Stage",
                entity_id=stage_id,
                details={"warehouse_id": stage["from_warehouse_id"], "items_count": len(items)}
            )
            self.uow.history.log_operation(audit_data)
            logging.info(f"На Складе ID {stage['from_warehouse_id']} успешно заблокирован резерв под этап {stage_id}")

    def ship_stage(self, employee_id: int, stage_id: int) -> None:
        """Фактическое списание остатков со склада и отправка этапа перевозки."""
        logging.info(f"Сотрудник ID {employee_id} инициировал отправку этапа ID {stage_id}")
        
        with self.uow:  
            # 1. Проверка существования этапа в БД
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise NotFoundError("Этап не найден.")
                
            # 2. Проверка ТЗ: этап должен быть в статусе «Черновик» или «Зарезервировано»
            if stage["status_id"] not in [StatusName.DRAFT, StatusName.RESERVED]:
                raise InvalidStatusError("Разрешено отправлять только этапы в статусе 'Черновик' или 'Зарезервировано'.")
                
            # 3. Проверка ТЗ: груз уходит именно со склада текущего сотрудника
            creator = self.uow.employee.get_by_id_with_permissions(employee_id)
            if not creator or creator.get("warehouse_id") != stage["from_warehouse_id"]:
                raise AccessDeniedError("Вы можете отправлять грузы только со своего склада.")
                
            # 4. Проверка ТЗ: в этапе физически есть добавленные товары
            items = self.uow.dispatch.get_stage_items(stage_id)
            if not items:
                raise ValidationError("Нельзя отправить этап перевозки без товаров.")
                
            # 5. Блокировка строк остатков в БД через FOR UPDATE (ТЗ: stock.get_many(..., for_update=True))
            product_ids = [item["product_id"] for item in items]
            stocks = self.uow.stock.get_many_for_update(warehouse_id=stage["from_warehouse_id"], product_ids=product_ids)
            stock_map = {s.product_id: s for s in stocks}

            # 6. Цикл обработки списаний со склада для каждого товара
            for item in items:
                p_id = item["product_id"]
                req_qty = float(item["document_quantity"])
                stock_row = stock_map.get(p_id)
                
                curr_qty = float(stock_row.quantity) if stock_row else 0.0
                curr_res = float(stock_row.reserved_quantity) if stock_row else 0.0

                # Сценарий А: Отправка напрямую из статуса «Черновик» (ТЗ: проверяет свободный остаток и уменьшает quantity)
                if stage["status_id"] == StatusName.DRAFT:
                    if (curr_qty - curr_res) < req_qty:
                        raise ValidationError(f"Недостаточно свободного товара ID {p_id} для мгновенной отправки.")
                    
                    self.uow.stock.decrease_quantity(
                        warehouse_id=stage["from_warehouse_id"], product_id=p_id, amount=req_qty
                    )

                # Сценарий Б: Отправка из предварительного «Резерва» (ТЗ: проверяет резерв, уменьшает quantity и reserved)
                elif stage["status_id"] == StatusName.RESERVED:
                    if curr_res < req_qty:
                        raise ValidationError(f"Ошибка резерва: заблокированный объем товара ID {p_id} меньше требуемого.")
                    
                    self.uow.stock.decrease_quantity_and_reservation(
                        warehouse_id=stage["from_warehouse_id"], product_id=p_id, amount=req_qty
                    )
            
            # 7. Фиксация отправки: проставляем статус SHIPPED и записываем sent_at
            self.uow.dispatch.mark_stage_as_shipped(
                stage_id=stage_id, 
                status_id=StatusName.SHIPPED, 
                sent_at=datetime.now(timezone.utc)
            )
            
            # ТЗ: Перевозка (весь shipment) тоже получает статус «Отправлено»
            self.uow.dispatch.update_shipment_status(stage["shipment_id"], status_id=StatusName.SHIPPED)
            
            # 8. Финальный аудит операции в историю
            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=employee_id,
                operation_type="STAGE_SHIPPED",
                entity_name="Stage",
                entity_id=stage_id,
                details={"from_warehouse_id": stage["from_warehouse_id"], "to_warehouse_id": stage["to_warehouse_id"]}
            )
            self.uow.history.log_operation(audit_data)
            
            logging.info(f"Транспорт выехал. Этап {stage_id} успешно отправлен, остатки скорректированы.")
