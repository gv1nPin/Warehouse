import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.Warehouse.BLL.Common import ShipmentStatus
from src.Warehouse.BLL.Services.ShipmentService.ShipmentReceiptService import (
    ShipmentReceiptService,
    BusinessLogicException,
    AccessDeniedException,
    EntityNotFoundException,
)


# === ФИКСТУРЫ ДЛЯ ДЕПОЗИТОРИЕВ И ЗАВИСИМОСТЕЙ ===

@pytest.fixture
def mock_shipment_repo():
    return Mock()


@pytest.fixture
def mock_employee_repo():
    return Mock()


@pytest.fixture
def mock_transit_coordinator():
    return Mock()


@pytest.fixture
def service(mock_shipment_repo, mock_employee_repo, mock_transit_coordinator):
    return ShipmentReceiptService(
        shipment_repo=mock_shipment_repo,
        employee_repo=mock_employee_repo,
        transit_coordinator=mock_transit_coordinator
    )


# === ТЕСТЫ ДЛЯ МЕТОДА: get_incoming_stages ===

class TestGetIncomingStages:

    def test_get_incoming_stages_success(self, service, mock_shipment_repo):
        """Успешное получение списка входящих этапов со статусом SHIPPED."""
        # Arrange
        expected_stages = [{"id": 1, "route": "A->B"}, {"id": 2, "route": "C->B"}]
        mock_shipment_repo.get_incoming_stages_by_warehouse.return_value = expected_stages

        # Act
        result = service.get_incoming_stages(warehouse_id=10)

        # Assert
        assert result == expected_stages
        mock_shipment_repo.get_incoming_stages_by_warehouse.assert_called_once_with(
            10, status_id=ShipmentStatus.SHIPPED
        )


# === ТЕСТЫ ДЛЯ МЕТОДА: enter_actual_quantity ===

class TestEnterActualQuantity:

    def test_enter_quantity_success(self, service, mock_shipment_repo):
        """Успешное обновление фактического количества товара на этапе в пути."""
        # Arrange
        mock_shipment_repo.get_stage_by_id.return_value = {"id": 1, "status_id": ShipmentStatus.SHIPPED}

        # Act
        service.enter_actual_quantity(stage_id=1, product_id=5, actual_quantity=15.5)

        # Assert
        mock_shipment_repo.update_item_actual_quantity.assert_called_once_with(1, 5, 15.5)

    def test_raise_exception_if_quantity_is_negative(self, service):
        """Ошибка, если передано отрицательное количество товара."""
        with pytest.raises(BusinessLogicException, match="Фактическое количество не может быть отрицательным."):
            service.enter_actual_quantity(stage_id=1, product_id=5, actual_quantity=-1.0)

    def test_raise_exception_if_stage_not_shipped(self, service, mock_shipment_repo):
        """Ошибка, если этап находится в любом статусе, кроме 'Отправлено' (SHIPPED)."""
        mock_shipment_repo.get_stage_by_id.return_value = {"id": 1, "status_id": ShipmentStatus.DRAFT}
        
        with pytest.raises(BusinessLogicException, match="Вносить фактическое количество можно только для грузов в пути."):
            service.enter_actual_quantity(stage_id=1, product_id=5, actual_quantity=10.0)


# === ТЕСТЫ ДЛЯ МЕТОДА: accept_stage ===

class TestAcceptStage:

    @pytest.fixture
    def setup_valid_stage_and_employee(self, mock_shipment_repo, mock_employee_repo):
        """Базовый корректный пресет данных для успешной приемки."""
        mock_shipment_repo.get_stage_by_id.return_value = {
            "id": 100, "shipment_id": 42, "stage_order": 1, "to_warehouse_id": 10
        }
        mock_employee_repo.get_by_id.return_value = {"id": 7, "warehouse_id": 10}
        mock_shipment_repo.get_stage_by_order.return_value = None  # По умолчанию это последний этап

    def test_accept_success_without_discrepancies_final_stage(self, service, mock_shipment_repo, setup_valid_stage_and_employee):
        """Успешное закрытие финального этапа без расхождений (статус RECEIVED)."""
        # Arrange
        mock_shipment_repo.get_stage_items.return_value = [
            {"product_id": 1, "document_quantity": 10.0, "actual_quantity": 10.0}
        ]
        fixed_now = datetime(2026, 9, 10, 12, 0, 0)

        with patch("your_module.datetime") as mock_datetime:  # Подменяем datetime для проверки даты
            mock_datetime.now.return_value = fixed_now

            # Act
            service.accept_stage(stage_id=100, employee_id=7)

            # Assert
            mock_shipment_repo.complete_stage.assert_called_once_with(
                stage_id=100, status_id=ShipmentStatus.RECEIVED, acceptor_id=7, received_at=fixed_now
            )
            # Так как это финальный этап (next_stage=None), закрывается вся перевозка целиком
            mock_shipment_repo.update_shipment_status.assert_called_once_with(42, status_id=ShipmentStatus.RECEIVED)

    def test_accept_success_with_discrepancies_final_stage(self, service, mock_shipment_repo, setup_valid_stage_and_employee):
        """Успешное закрытие финального этапа с расхождениями количества (статус DISCREPANCY)."""
        # Arrange
        mock_shipment_repo.get_stage_items.return_value = [
            {"product_id": 1, "document_quantity": 10.0, "actual_quantity": 9.5}  # Есть расхождение
        ]

        # Act
        service.accept_stage(stage_id=100, employee_id=7)

        # Assert
        mock_shipment_repo.complete_stage.assert_called_once_with(
            stage_id=100, status_id=ShipmentStatus.DISCREPANCY, acceptor_id=7, received_at=pytest.any(datetime)
        )
        mock_shipment_repo.update_shipment_status.assert_called_once_with(42, status_id=ShipmentStatus.DISCREPANCY)

    def test_accept_success_triggers_transit_to_next_stage(self, service, mock_shipment_repo, mock_transit_coordinator, setup_valid_stage_and_employee):
        """Если есть следующий этап, приемка должна инициировать транзит через transit_coordinator."""
        # Arrange
        mock_shipment_repo.get_stage_items.return_value = [
            {"product_id": 1, "document_quantity": 10.0, "actual_quantity": 10.0}
        ]
        # Имитируем, что есть следующий этап маршрута
        mock_shipment_repo.get_stage_by_order.return_value = {"id": 101, "stage_order": 2}

        # Act
        service.accept_stage(stage_id=100, employee_id=7)

        # Assert
        # Проверяем, что управление передалось координатору транзита
        mock_transit_coordinator.move_to_next_stage.assert_called_once_with(
            100, 101, {1: 10.0}
        )
        # Статус всей перевозки (update_shipment_status) НЕ должен обновляться, пока маршрут не окончен
        mock_shipment_repo.update_shipment_status.assert_not_called()

    def test_raise_exception_if_stage_not_found(self, service, mock_shipment_repo):
        """Ошибка, если принимаемый этап не существует."""
        mock_shipment_repo.get_stage_by_id.return_value = None
        
        with pytest.raises(EntityNotFoundException, match="Этап не найден."):
            service.accept_stage(stage_id=404, employee_id=7)

    def test_raise_exception_if_employee_not_found(self, service, mock_shipment_repo, mock_employee_repo):
        """Ошибка, если принимающий сотрудник не найден в системе."""
        mock_shipment_repo.get_stage_by_id.return_value = {"id": 100}
        mock_employee_repo.get_by_id.return_value = None
        
        with pytest.raises(EntityNotFoundException, match="Сотрудник приёмки не найден."):
            service.accept_stage(stage_id=100, employee_id=999)

    def test_raise_exception_if_employee_from_different_warehouse(self, service, mock_shipment_repo, mock_employee_repo):
        """Ошибка доступа, если склад сотрудника не совпадает со складом назначения груза."""
        mock_shipment_repo.get_stage_by_id.return_value = {"id": 100, "to_warehouse_id": 10}
        mock_employee_repo.get_by_id.return_value = {"id": 7, "warehouse_id": 99} # Другой склад
        
        with pytest.raises(AccessDeniedException, match="Вы не можете принять груз, направленный на чужой склад."):
            service.accept_stage(stage_id=100, employee_id=7)

    def test_raise_exception_if_actual_quantity_is_null(self, service, mock_shipment_repo, setup_valid_stage_and_employee):
        """Ошибка, если у какого-либо товара на этапе не заполнено фактическое количество (None)."""
        mock_shipment_repo.get_stage_items.return_value = [
            {"product_id": 1, "document_quantity": 10.0, "actual_quantity": 10.0},
            {"product_id": 2, "document_quantity": 5.0, "actual_quantity": None} # Не заполнено!
        ]
        
        with pytest.raises(BusinessLogicException, match="Заполните фактическое количество для товара ID 2."):
            service.accept_stage(stage_id=100, employee_id=7)
