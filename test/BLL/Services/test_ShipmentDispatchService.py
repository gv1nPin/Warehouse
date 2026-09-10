import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

from src.Warehouse.BLL.Common import ShipmentStatus
from src.Warehouse.BLL.Services.ShipmentService.ShipmentDispatchService import (
    ShipmentDispatchService,
    BusinessLogicException,
    InsufficientStockException,
    EntityNotFoundException
)


@pytest.fixture
def mock_shipment_repo():
    return Mock()


@pytest.fixture
def mock_stock_repo():
    return Mock()


@pytest.fixture
def mock_employee_repo():
    return Mock()


@pytest.fixture
def service(mock_shipment_repo, mock_stock_repo, mock_employee_repo):
    return ShipmentDispatchService(
        shipment_repo=mock_shipment_repo,
        stock_repo=mock_stock_repo,
        employee_repo=mock_employee_repo
    )


# ==============================================================================
# ТЕСТЫ: create_shipment_draft
# ==============================================================================

def test_create_shipment_draft_success(service, mock_employee_repo, mock_shipment_repo):
    # Arrange
    mock_employee_repo.get_by_id.return_value = {"id": 1, "name": "Ivan"}
    mock_shipment_repo.create_shipment.return_value = 100
    
    planned_date = date.today() + timedelta(days=1)
    route_warehouses = [10, 20, 30]

    # Act
    shipment_id = service.create_shipment_draft(
        creator_id=1, 
        planned_date=planned_date, 
        route_warehouses=route_warehouses
    )

    # Assert
    assert shipment_id == 100
    mock_employee_repo.get_by_id.assert_called_once_with(1)
    mock_shipment_repo.create_shipment.assert_called_once_with(
        status_id=ShipmentStatus.DRAFT, 
        creator_id=1, 
        planned_date=planned_date
    )
    # Должно создаться 2 этапа для 3-х складов (10->20, 20->30)
    assert mock_shipment_repo.create_stage.call_count == 2


def test_create_shipment_draft_past_date_raises_exception(service):
    past_date = date.today() - timedelta(days=1)
    with pytest.raises(BusinessLogicException, match="Плановая дата не может быть в прошлом."):
        service.create_shipment_draft(creator_id=1, planned_date=past_date, route_warehouses=[1, 2])


@pytest.mark.parametrize("route", [[], [1]])
def test_create_shipment_draft_invalid_route_raises_exception(service, route):
    with pytest.raises(BusinessLogicException, match="Маршрут должен содержать как минимум"):
        service.create_shipment_draft(creator_id=1, planned_date=date.today(), route_warehouses=route)


def test_create_shipment_draft_employee_not_found(service, mock_employee_repo):
    mock_employee_repo.get_by_id.return_value = None
    with pytest.raises(EntityNotFoundException, match="Сотрудник-создатель не найден."):
        service.create_shipment_draft(creator_id=999, planned_date=date.today(), route_warehouses=[1, 2])


# ==============================================================================
# ТЕСТЫ: add_item_to_stage
# ==============================================================================

def test_add_item_to_stage_success(service, mock_shipment_repo, mock_stock_repo):
    # Arrange
    mock_shipment_repo.get_stage_by_id.return_value = {
        "id": 50, "from_warehouse_id": 10, "status_id": ShipmentStatus.DRAFT
    }
    mock_stock_repo.get_balance.return_value = {"quantity": 100.0, "reserved_quantity": 20.0}

    # Act
    service.add_item_to_stage(stage_id=50, product_id=5, document_quantity=50.0)

    # Assert
    mock_shipment_repo.add_item_to_stage.assert_called_once_with(50, 5, 50.0)


@pytest.mark.parametrize("quantity", [0.0, -5.5])
def test_add_item_to_stage_invalid_quantity_raises_exception(service, quantity):
    with pytest.raises(BusinessLogicException, match="Количество должно быть больше нуля."):
        service.add_item_to_stage(stage_id=50, product_id=5, document_quantity=quantity)


def test_add_item_to_stage_not_found(service, mock_shipment_repo):
    mock_shipment_repo.get_stage_by_id.return_value = None
    with pytest.raises(EntityNotFoundException, match="Указанный этап перевозки не найден."):
        service.add_item_to_stage(stage_id=404, product_id=5, document_quantity=10.0)


def test_add_item_to_stage_wrong_status(service, mock_shipment_repo):
    mock_shipment_repo.get_stage_by_id.return_value = {
        "id": 50, "from_warehouse_id": 10, "status_id": ShipmentStatus.RESERVED
    }
    with pytest.raises(BusinessLogicException, match="Добавление товаров разрешено только в статусе 'Черновик'."):
        service.add_item_to_stage(stage_id=50, product_id=5, document_quantity=10.0)


def test_add_item_to_stage_insufficient_stock(service, mock_shipment_repo, mock_stock_repo):
    # Arrange: доступно 80 (100 - 20), а запрашиваем 90
    mock_shipment_repo.get_stage_by_id.return_value = {
        "id": 50, "from_warehouse_id": 10, "status_id": ShipmentStatus.DRAFT
    }
    mock_stock_repo.get_balance.return_value = {"quantity": 100.0, "reserved_quantity": 20.0}

    # Act & Assert
    with pytest.raises(InsufficientStockException, match="Недостаточно свободного товара для резерва"):
        service.add_item_to_stage(stage_id=50, product_id=5, document_quantity=90.0)


# ==============================================================================
# ТЕСТЫ: reserve_stage_items
# ==============================================================================

def test_reserve_stage_items_success(service, mock_shipment_repo, mock_stock_repo):
    # Arrange
    mock_shipment_repo.get_stage_by_id.return_value = {"id": 50, "from_warehouse_id": 10}
    mock_shipment_repo.get_stage_items.return_value = [
        {"product_id": 1, "document_quantity": 10.0},
        {"product_id": 2, "document_quantity": 5.5}
    ]

    # Act
    service.reserve_stage_items(stage_id=50)

    # Assert
    assert mock_stock_repo.increase_reservation.call_count == 2
    mock_stock_repo.increase_reservation.assert_any_call(warehouse_id=10, product_id=1, amount=10.0)
    mock_stock_repo.increase_reservation.assert_any_call(warehouse_id=10, product_id=2, amount=5.5)
    mock_shipment_repo.update_stage_status.assert_called_once_with(50, status_id=ShipmentStatus.RESERVED)


def test_reserve_stage_items_not_found(service, mock_shipment_repo):
    mock_shipment_repo.get_stage_by_id.return_value = None
    with pytest.raises(EntityNotFoundException, match="Этап не найден."):
        service.reserve_stage_items(stage_id=404)


def test_reserve_stage_items_empty_stage(service, mock_shipment_repo):
    mock_shipment_repo.get_stage_by_id.return_value = {"id": 50, "from_warehouse_id": 10}
    mock_shipment_repo.get_stage_items.return_value = []  # пустой список
    
    with pytest.raises(BusinessLogicException, match="Невозможно зарезервировать пустой этап."):
        service.reserve_stage_items(stage_id=50)


# ==============================================================================
# ТЕСТЫ: ship_stage
# ==============================================================================

def test_ship_stage_success(service, mock_shipment_repo):
    # Arrange
    mock_shipment_repo.get_stage_by_id.return_value = {
        "id": 50, "status_id": ShipmentStatus.RESERVED
    }

    # Фиксируем время, чтобы сравнить его внутри assert_called_once_with
    fixed_now = datetime(2026, 9, 10, 12, 0, 0)
    
    with patch('src.Warehouse.BLL.Services.ShipmentService.ShipmentDispatchService.datetime') as mock_datetime:
        mock_datetime.now.return_value = fixed_now

        # Act
        service.ship_stage(stage_id=50)

        # Assert
        mock_shipment_repo.mark_stage_as_shipped.assert_called_once_with(50, sent_at=fixed_now)


def test_ship_stage_not_found(service, mock_shipment_repo):
    mock_shipment_repo.get_stage_by_id.return_value = None
    with pytest.raises(EntityNotFoundException, match="Этап не найден."):
        service.ship_stage(stage_id=404)


def test_ship_stage_wrong_status(service, mock_shipment_repo):
    mock_shipment_repo.get_stage_by_id.return_value = {
        "id": 50, "status_id": ShipmentStatus.DRAFT  # Не зарезервирован
    }
    with pytest.raises(BusinessLogicException, match="Разрешено отправлять только зарезервированные этапы"):
        service.ship_stage(stage_id=50)
