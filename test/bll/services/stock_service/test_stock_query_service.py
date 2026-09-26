import unittest
from unittest import mock

from warehouse.bll.services.auth_service import AccessService
from warehouse.bll.services.stock_service import StockQueryService
from warehouse.common import PermissionName
from warehouse.common.dto import EmployeeDTO
from warehouse.common.exceptions import AccessDeniedError

KEEPER = EmployeeDTO(
    id=2, first_name='Мария', last_name='Кузнецова', login='keeper',
    role_id=4, role_name='Кладовщик', warehouse_id=3, is_deleted=False,
)


class StockQueryServiceTests(unittest.TestCase):
    def setUp(self):
        self.uow = mock.MagicMock()
        self.uow.__enter__.return_value = self.uow
        self.uow.employees.get_by_id.return_value = KEEPER
        self.service = StockQueryService(uow_factory=lambda: self.uow, access=AccessService())

    def test_keeper_sees_own_warehouse(self):
        self.uow.employees.get_permissions.return_value = [PermissionName.SHIPMENT_DISPATCH]
        self.service.list_stock(KEEPER.id)
        self.uow.stock.list_by_warehouse.assert_called_once_with(3)

    def test_driver_and_manager_are_denied(self):
        for permissions in ([], [PermissionName.SHIPMENT_CANCEL, PermissionName.SHIPMENT_VIEW_ALL]):
            with self.subTest(permissions=permissions):
                self.uow.employees.get_permissions.return_value = permissions
                with self.assertRaises(AccessDeniedError):
                    self.service.list_stock(KEEPER.id)


if __name__ == '__main__':
    unittest.main()
