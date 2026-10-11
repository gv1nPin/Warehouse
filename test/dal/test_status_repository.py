import unittest
from unittest import mock

from warehouse.common import StatusName
from warehouse.common.exceptions import NotFoundError
from warehouse.dal.repositories.status_repository import StatusRepository


class StatusRepositoryRequireIdTests(unittest.TestCase):
    def setUp(self):
        self.session = mock.MagicMock()
        self.repo = StatusRepository(self.session)

    def test_returns_id_when_status_exists(self):
        self.session.scalar.return_value = 4
        self.assertEqual(self.repo.require_id(StatusName.RESERVED), 4)

    def test_missing_status_raises_not_found_with_name(self):
        self.session.scalar.return_value = None
        with self.assertRaises(NotFoundError) as ctx:
            self.repo.require_id(StatusName.CANCELLED)
        self.assertIn(StatusName.CANCELLED.value, ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
