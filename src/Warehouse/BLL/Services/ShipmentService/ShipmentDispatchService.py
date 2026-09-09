from datetime import date, datetime
from typing import List
from src.Warehouse.BLL.Interfaces.ShipmentService import AbstractShipmentDispatchService
from src.Warehouse.BLL.Common import ShipmentStatus


class BusinessLogicException(Exception): pass
class InsufficientStockException(Exception): pass
class EntityNotFoundException(Exception): pass


class ShipmentDispatchService(AbstractShipmentDispatchService):
    def __init__(self, shipment_repo, stock_repo, employee_repo):
        """Инициализирует сервис управления отправкой грузов и планирования маршрутов.

        Args:
            shipment_repo: Репозиторий из слоя DAL для управления перевозками и этапами.
            stock_repo: Репозиторий из слоя DAL для контроля остатков и резервирования.
            employee_repo: Репозиторий из слоя DAL для работы с сотрудниками.
        """
        self.shipment_repo = shipment_repo
        self.stock_repo = stock_repo
        self.employee_repo = employee_repo

    def create_shipment_draft(self, creator_id: int, planned_date: date, route_warehouses: List[int]) -> int:
        """Создает базовую запись перевозки (Shipments) и генерирует для нее последовательную 
        цепочку транзитных этапов (ShipmentStages) на основе переданного массива складов.

        Args:
            creator_id (int): Идентификатор сотрудника (кладовщика-отправителя), создающего черновик.
            planned_date (date): Планируемая дата отправления груза с начальной точки маршрута.
            route_warehouses (List[int]): Массив ID складов, выстроенных по порядку следования груза.

        Raises:
            BusinessLogicException: Если плановая дата в прошлом или в маршруте менее 2 складов.
            EntityNotFoundException: Если сотрудник-создатель не найден в базе данных.

        Returns:
            int: Идентификатор (ID) созданной сквозной перевозки.
        """
        if planned_date < date.today():
            raise BusinessLogicException("Плановая дата не может быть в прошлом.")
        if len(route_warehouses) < 2:
            raise BusinessLogicException("Маршрут должен содержать как минимум склад-отправитель и склад-получатель.")
        
        creator = self.employee_repo.get_by_id(creator_id)
        if not creator:
            raise EntityNotFoundException("Сотрудник-создатель не найден.")
        
        shipment_id = self.shipment_repo.create_shipment(
            status_id=ShipmentStatus.DRAFT, 
            creator_id=creator_id, 
            planned_date=planned_date
        )
        
        for i in range(len(route_warehouses) - 1):
            from_wh = route_warehouses[i]
            to_wh = route_warehouses[i + 1]
            stage_order = i + 1
            initial_stage_status = ShipmentStatus.DRAFT if stage_order == 1 else ShipmentStatus.IN_WAITING 
            
            self.shipment_repo.create_stage(
                shipment_id=shipment_id,
                stage_order=stage_order,
                from_warehouse_id=from_wh,
                to_warehouse_id=to_wh,
                status_id=initial_stage_status
            )
            
        return shipment_id

    def add_item_to_stage(self, stage_id: int, product_id: int, document_quantity: float) -> None:
        """Добавляет товарную позицию в состав конкретного этапа перевозки (StageItems). 
        Перед добавлением проверяет, что на складе отправления этапа достаточно свободного товара.

        Args:
            stage_id (int): Идентификатор этапа (ShipmentStages), в который добавляется товар.
            product_id (int): Идентификатор добавляемого товара (Products).
            document_quantity (float): Плановое количество товара для отправки по документам.

        Raises:
            BusinessLogicException: Если количество <= 0 или этап находится не в статусе 'Черновик'.
            EntityNotFoundException: Если указанный этап перевозки не существует в системе.
            InsufficientStockException: Если доступный остаток (с учетом текущих резервов) меньше требуемого.
        """
        if document_quantity <= 0:
            raise BusinessLogicException("Количество должно быть больше нуля.")
        
        stage = self.shipment_repo.get_stage_by_id(stage_id)
        if not stage:
            raise EntityNotFoundException("Указанный этап перевозки не найден.")
            
        if stage["status_id"] != ShipmentStatus.DRAFT:
            raise BusinessLogicException("Добавление товаров разрешено только в статусе 'Черновик'.")
        
        stock = self.stock_repo.get_balance(stage["from_warehouse_id"], product_id)
        quantity = stock["quantity"] if stock else 0.0
        reserved_quantity = stock["reserved_quantity"] if stock else 0.0
        
        if (quantity - reserved_quantity) < document_quantity:
            raise InsufficientStockException(
                f"Недостаточно свободного товара для резерва. Доступно: {quantity - reserved_quantity}"
            )
        
        self.shipment_repo.add_item_to_stage(stage_id, product_id, document_quantity)

    def reserve_stage_items(self, stage_id: int) -> None:
        """Переводит добавленные в накладную товары текущего этапа из свободного остатка в резерв 
        на складе отправления. Фиксирует статус этапа как 'Зарезервировано'.

        Args:
            stage_id (int): Идентификатор этапа перевозки, содержимое которого нужно заблокировать.

        Raises:
            EntityNotFoundException: Если указанный этап перевозки не найден.
            BusinessLogicException: Если в этапе отсутствуют добавленные товары (пустой груз).
        """
        stage = self.shipment_repo.get_stage_by_id(stage_id)
        if not stage:
            raise EntityNotFoundException("Этап не найден.")
            
        items = self.shipment_repo.get_stage_items(stage_id)
        if not items:
            raise BusinessLogicException("Невозможно зарезервировать пустой этап.")
            
        for item in items:
            self.stock_repo.increase_reservation(
                warehouse_id=stage["from_warehouse_id"], 
                product_id=item["product_id"], 
                amount=item["document_quantity"]
            )
            
        self.shipment_repo.update_stage_status(stage_id, status_id=ShipmentStatus.RESERVED)

    def ship_stage(self, stage_id: int) -> None:
        """Фиксирует физический выезд машины со склада отправления. Устанавливает статус 
        этапа 'Отправлено' и дату выезда. Окончательное списание с баланса склада выполнит СУБД.

        Args:
            stage_id (int): Идентификатор отправляемого этапа.

        Raises:
            EntityNotFoundException: Если указанный этап перевозки не найден.
            BusinessLogicException: Если этап не был предварительно переведен в статус 'Зарезервировано'.
        """
        stage = self.shipment_repo.get_stage_by_id(stage_id)
        if not stage:
            raise EntityNotFoundException("Этап не найден.")
            
        if stage["status_id"] != ShipmentStatus.RESERVED:
            raise BusinessLogicException("Разрешено отправлять только зарезервированные этапы грузов.")
            
        self.shipment_repo.mark_stage_as_shipped(stage_id, sent_at=datetime.now())
