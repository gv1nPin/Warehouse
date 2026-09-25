import unittest
from unittest import mock

from warehouse.bll.interfaces.auth_service import ActorDTO
from warehouse.bll.services.auth_service import AccessService
from warehouse.bll.services.employee_service import EmployeeService
from warehouse.common import PermissionName
from warehouse.common.dto import EmployeeDTO, NewEmployee, WarehouseDTO
from warehouse.common.exceptions import AccessDeniedError, NotFoundError, ValidationError
from warehouse.common.security import verify_password

ADMIN = EmployeeDTO(
    id=1, first_name='Анна', last_name='Смирнова', login='admin',
    role_id=3, role_name='Администратор системы', warehouse_id=1, is_deleted=False,
)
NEW = NewEmployee(
    first_name=' Пётр ', last_name='Сидоров', login='sidorov',
    password='password1', warehouse_id=1, role_id=6,
)


class EmployeeServiceTests(unittest.TestCase):
    def setUp(self):
        self.uow = mock.MagicMock()
        self.uow.__enter__.return_value = self.uow
        self.uow.employees.get_by_id.return_value = ADMIN
        self.uow.employees.get_permissions.return_value = [PermissionName.EMPLOYEE_MANAGE]
        self.uow.employees.login_exists.return_value = False
        self.uow.employees.create.return_value = 42
        self.uow.warehouses.get_by_id.return_value = WarehouseDTO(id=1, title='Север', address='')
        self.uow.roles.get_name.return_value = 'Водитель'
        self.service = EmployeeService(uow_factory=lambda: self.uow, access=AccessService())

    def test_register_hashes_password_and_trims_names(self):
        self.service.register(ADMIN.id, NEW)
        kwargs = self.uow.employees.create.call_args.kwargs
        self.assertEqual(kwargs['first_name'], 'Пётр')
        self.assertTrue(verify_password('password1', kwargs['password_hash']))
        self.uow.employees.get_by_id.assert_called_with(42)

    def test_login_taken(self):
        self.uow.employees.login_exists.return_value = True
        with self.assertRaisesRegex(ValidationError, 'Логин «sidorov» уже занят'):
            self.service.register(ADMIN.id, NEW)
        self.uow.employees.create.assert_not_called()

    def test_short_password(self):
        with self.assertRaises(ValidationError):
            self.service.register(ADMIN.id, NewEmployee(**{**_fields(NEW), 'password': 'short'}))

    def test_unknown_role(self):
        self.uow.roles.get_name.return_value = None
        with self.assertRaises(NotFoundError):
            self.service.register(ADMIN.id, NEW)

    def test_only_admin(self):
        self.uow.employees.get_permissions.return_value = [PermissionName.SHIPMENT_CREATE]
        with self.assertRaises(AccessDeniedError):
            self.service.register(ADMIN.id, NEW)
        with self.assertRaises(AccessDeniedError):
            self.service.list_roles(ADMIN.id)

    def test_roles_sorted_by_id(self):
        self.uow.roles.list_all.return_value = {6: 'Водитель', 1: 'Старший кладовщик'}
        self.assertEqual([r.id for r in self.service.list_roles(ADMIN.id)], [1, 6])


def _fields(employee: NewEmployee) -> dict:
    return {name: getattr(employee, name) for name in employee.__dataclass_fields__}


if __name__ == '__main__':
    unittest.main()
