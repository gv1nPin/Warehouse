import logging
from datetime import datetime, timezone 
from typing import List, Optional
from warehouse.common import constants
from warehouse.api.dto import StageDTO, StageItemDTO 
from warehouse.bll.interfaces.shipment_service.abstract_shipment_receipt_service import AbstractShipmentReceiptService

class BusinessLogicException(Exception): pass
class AccessDeniedException(Exception): pass
class EntityNotFoundException(Exception): pass

class ShipmentReceiptService(AbstractShipmentReceiptService):
    def __init__(self, uow):
        self.uow = uow

    def get_incoming(self, employee_id: int) -> List[StageDTO]:
        """Получает этапы в статусе 'Отправлено', которые едут на склад сотрудника."""
        employee = self.uow.employees.get_by_id_with_permissions(employee_id)
        if not employee:
            raise EntityNotFoundException("Сотрудник не найден.")
            
        raw_stages = self.uow.stages.get_incoming_stages_by_warehouse(
            warehouse_id=employee["warehouse_id"], 
            status_id=constants.SHIPPED
        )
        # Собираем DTO напрямую через конструктор класса DTO
        return [StageDTO(**stage) for stage in raw_stages]

    def enter_actual_quantity(self, employee_id: int, item_id: int, quantity: float, comment: Optional[str] = None) -> None:
        """Вносит фактическое количество товара с проверками периметра и комментариев."""
        if quantity is None or quantity < 0:
            raise BusinessLogicException("Количество должно быть заполнено и не может быть отрицательным.")
            
        with self.uow:
            item = self.uow.stage_items.get_stage_item_by_id(item_id)
            if not item:
                raise EntityNotFoundException("Позиция этапа не найдена.")
                
            stage = self.uow.stages.get_stage_by_id(item["stage_id"])
            if not stage or stage["status_id"] != constants.SHIPPED:
                raise BusinessLogicException("Вносить изменения можно только для этапов в статусе 'Отправлено'.")
                
            employee = self.uow.employees.get_by_id_with_permissions(employee_id)
            if not employee or employee["warehouse_id"] != stage["to_warehouse_id"]:
                raise AccessDeniedException("Вы не можете изменять данные груза, направленного на чужой склад.")
            
            if float(quantity) != float(item["document_quantity"]) and not comment:
                raise BusinessLogicException("При расхождении факта и документа комментарий обязателен.")
                
            self.uow.stage_items.set_actual_quantity(item_id, quantity, comment)
            logging.info(f"Сотрудник {employee_id} внес факт по позиции {item_id}: {quantity} (Комментарий: {comment})")

    def check_discrepancies(self, employee_id: int, stage_id: int) -> List[StageItemDTO]:
        """Возвращает элементы StageItems без факта и позиции с несовпадением документов. Ничего не меняет в БД."""
        stage = self.uow.stages.get_stage_by_id(stage_id)
        if not stage:
            raise EntityNotFoundException("Этап не найден.")
            
        stage_items = self.uow.stage_items.get_stage_items(stage_id)
        discrepancies = []
        
        for item in stage_items:
            # Сверка по полям вашей таблицы StageItems
            if item["actual_quantity"] is None or float(item["actual_quantity"]) != float(item["document_quantity"]):
                # Собираем DTO без стороннего маппера
                discrepancies.append(StageItemDTO(**item))
                
        return discrepancies

    def accept_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Принимает этап, обновляет остатки, рассчитывает и переключает логистические шаги."""
        logging.info(f"Сотрудник ID {employee_id} закрывает приёмку для этапа ID {stage_id}")
        with self.uow:  
            stage = self.uow.stages.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Этап не найден.")
                
            if stage["status_id"] != constants.SHIPPED:
                raise BusinessLogicException("Принять можно только этап в статусе 'Отправлено'.")
                
            employee = self.uow.employees.get_by_id_with_permissions(employee_id)
            if not employee:
                raise EntityNotFoundException("Сотрудник приёмки не найден.")
                
            if "shipment:accept" not in employee.get("permissions", []):
                raise AccessDeniedException("У вашей роли нет права 'shipment:accept' на приемку грузов.")
                
            if employee["warehouse_id"] != stage["to_warehouse_id"]:
                # Формируем словарь структуры лога напрямую в сервисе
                failed_audit = {
                    "employee_id": employee_id,
                    "operation_type": "SECURITY_PERIMETER_VIOLATION",
                    "entity_name": "Stage",
                    "entity_id": stage_id,
                    "details": {"employee_warehouse": employee["warehouse_id"], "target_warehouse": stage["to_warehouse_id"]}
                }
                self.uow.history.log_operation(failed_audit)
                raise AccessDeniedException("Вы не можете принять груз, направленный на чужой склад.")
            
            stage_items = self.uow.stage_items.get_stage_items(stage_id)
            
            unfilled_items = [item for item in stage_items if item["actual_quantity"] is None]
            if unfilled_items:
                raise BusinessLogicException("Заполните факт по всем позициям перед финальной приемкой.")
            
            has_discrepancies = any(float(item["actual_quantity"]) != float(item["document_quantity"]) for item in stage_items)
            final_status = constants.DISCREPANCY if has_discrepancies else constants.RECEIVED
            
            # 1. Завершаем текущий этап
            self.uow.stages.complete_stage(
                stage_id=stage_id, 
                status_id=final_status, 
                acceptor_id=employee_id, 
                received_at=datetime.now(timezone.utc)
            )
            
            # 2. Начисляем остатки на склад получателя
            for item in stage_items:
                act_qty = float(item["actual_quantity"])
                if act_qty > 0:
                    self.uow.stock.add_quantity(
                        warehouse_id=stage["to_warehouse_id"], 
                        product_id=item["product_id"], 
                        quantity=act_qty
                    )
            
            # Формируем структуру лога успешного завершения приемки напрямую
            audit_data = {
                "employee_id": employee_id,
                "operation_type": "STAGE_ACCEPTED_RECEIVED" if not has_discrepancies else "STAGE_ACCEPTED_WITH_DISCREPANCY",
                "entity_name": "Stage",
                "entity_id": stage_id,
                "details": {"warehouse_id": employee["warehouse_id"]}
            }
            self.uow.history.log_operation(audit_data)

            # 3. ВНУТРЕННЯЯ ЛОГИКА ТРАНЗИТА
            next_stage = self.uow.stages.get_stage_by_order(
                shipment_id=stage["shipment_id"], 
                stage_order=stage["stage_order"] + 1
            )
            
            if next_stage:
                self.uow.stages.update_stage_status(next_stage["id"], status_id=constants.PROCESSING)
                
                for item in stage_items:
                    self.uow.stage_items.update_next_stage_item_document_quantity(
                        next_stage_id=next_stage["id"],
                        product_id=item["product_id"],
                        new_document_quantity=float(item["actual_quantity"])
                    )
            else:
                self.uow.shipments.update_shipment_status(stage["shipment_id"], status_id=final_status)
                logging.info(f"Поставка {stage['shipment_id']} полностью завершила свой маршрут.")
            
            updated_stage = self.uow.stages.get_stage_by_id(stage_id)
            return StageDTO(**updated_stage)
