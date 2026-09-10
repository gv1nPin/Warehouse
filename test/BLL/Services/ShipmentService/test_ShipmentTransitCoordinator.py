import pytest
from unittest.mock import Mock

from src.Warehouse.BLL.Common import ShipmentStatus
from src.Warehouse.BLL.Services.ShipmentService.ShipmentTransitCoordinator import ShipmentTransitCoordinator


@pytest.fixture
def mock_shipment_repo():
    """Создает мок для репозитория перевозок."""
    repo = Mock()
    # Дефолтный ответ при запросе информации о следующем этапе
    repo.get_stage_by_id.return_value = {
        "id": 200,
        "shipment_id": 42,
        "stage_order": 2
    }
    return repo


@pytest.fixture
def mock_dispatch_service():
    """Создает мок для сервиса отправки грузов."""
    return Mock()


@pytest.fixture
def coordinator(mock_shipment_repo, mock_dispatch_service):
    """Инициализирует тестируемый координатор транзита с моками."""
    return ShipmentTransitCoordinator(
        shipment_repo=mock_shipment_repo,
        dispatch_service=mock_dispatch_service
    )


# === ТЕСТЫ ДЛЯ МЕТОДА: move_to_next_stage ===

class TestMoveToNextStage:

    def test_move_to_next_stage_success(self, coordinator, mock_shipment_repo, mock_dispatch_service):
        """Успешный перенос доехавших товаров на следующий этап и запуск бронирования."""
        # Arrange
        accepted_items = {
            101: 15.0,  # Товар 101 доехал в количестве 15 шт.
            102: 5.5,   # Товар 102 доехал в количестве 5.5 шт.
            103: 0.0    # Товар 103 не доехал (0 шт.), его переносить не нужно
        }

        # Act
        coordinator.move_to_next_stage(
            current_stage_id=199, 
            next_stage_id=200, 
            accepted_items=accepted_items
        )

        # Assert
        # 1. Проверяем получение информации о следующем этапе
        mock_shipment_repo.get_stage_by_id.assert_called_once_with(200)

        # 2. Проверяем смену статуса всей перевозки на 'На транзитном складе'
        mock_shipment_repo.update_shipment_status.assert_called_once_with(
            42, status_id=ShipmentStatus.IN_TRANSIT_WH
        )

        # 3. Проверяем, что перенесли только товары с количеством > 0 (101 и 102)
        assert mock_shipment_repo.add_item_to_stage.call_count == 2
        mock_shipment_repo.add_item_to_stage.assert_any_call(
            stage_id=200, product_id=101, document_quantity=15.0
        )
        mock_shipment_repo.add_item_to_stage.assert_any_call(
            stage_id=200, product_id=102, document_quantity=5.5
        )
        # Убеждаемся, что пустой товар 103 не добавлялся
        assert {"product_id": 103} not in [call.kwargs.get("product_id") for call in mock_shipment_repo.add_item_to_stage.call_args_list]

        # 4. Проверяем, что статус следующего этапа переведен в 'Черновик'
        mock_shipment_repo.update_stage_status.assert_called_once_with(
            200, status_id=ShipmentStatus.DRAFT
        )

        # 5. Проверяем, что вызвано автоматическое бронирование через dispatch_service
        mock_dispatch_service.reserve_stage_items.assert_called_once_with(200)

    def test_move_to_next_stage_no_items_to_forward(self, coordinator, mock_shipment_repo, mock_dispatch_service):
        """Проверка транзита, если абсолютно все товары не доехали (пустой груз)."""
        # Arrange
        accepted_items = {
            101: 0.0,
            102: 0.0
        }

        # Act
        coordinator.move_to_next_stage(
            current_stage_id=199, 
            next_stage_id=200, 
            accepted_items=accepted_items
        )

        # Assert
        # Перевозка и этап все равно должны обновить статусы
        mock_shipment_repo.update_shipment_status.assert_called_once_with(42, status_id=ShipmentStatus.IN_TRANSIT_WH)
        mock_shipment_repo.update_stage_status.assert_called_once_with(200, status_id=ShipmentStatus.DRAFT)

        # Товары добавляться не должны
        mock_shipment_repo.add_item_to_stage.assert_not_called()

        # Бронирование dispatch_service НЕ должно вызываться, так как нечего форвардить
        mock_dispatch_service.reserve_stage_items.assert_not_called()
