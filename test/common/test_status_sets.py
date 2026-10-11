import unittest

from warehouse.common import ACTIVE_STATUSES, NOT_SHIPPED_STATUSES, StatusName


class StatusSetsTests(unittest.TestCase):
    def test_sets_contain_only_known_statuses_without_repeats(self):
        for statuses in (ACTIVE_STATUSES, NOT_SHIPPED_STATUSES):
            self.assertTrue(all(isinstance(s, StatusName) for s in statuses))
            self.assertEqual(len(set(statuses)), len(statuses))

    def test_not_shipped_is_part_of_active(self):
        self.assertLess(set(NOT_SHIPPED_STATUSES), set(ACTIVE_STATUSES))

    def test_shipped_is_active_but_not_cancellable(self):
        self.assertIn(StatusName.SHIPPED, ACTIVE_STATUSES)
        self.assertNotIn(StatusName.SHIPPED, NOT_SHIPPED_STATUSES)
        self.assertNotIn(StatusName.CANCELLED, ACTIVE_STATUSES)


if __name__ == "__main__":
    unittest.main()
