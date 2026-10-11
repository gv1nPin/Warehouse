import unittest

from warehouse.common import OperationType
from warehouse.common.log_details_formatter import LogDetailsFormatter

# Операции, которые намеренно идут в _format_default (отдельного обработчика нет).
DEFAULT_ONLY = {
    OperationType.LOGIN,
    OperationType.SHIPMENT_DELETE,
    OperationType.SHIPMENT_CANCEL,
    OperationType.ITEM_REMOVE,
    OperationType.DOCUMENT_ATTACH,
    OperationType.DOCUMENT_REMOVE,
    OperationType.STAGE_RESERVE,
}


class LogDetailsFormatterTests(unittest.TestCase):
    def test_driver_assign_marks_reassignment(self):
        reassigned = LogDetailsFormatter.format(
            OperationType.DRIVER_ASSIGN, {"driver_id": 5, "previous_driver_id": 3}
        )
        assigned = LogDetailsFormatter.format(
            OperationType.DRIVER_ASSIGN, {"driver_id": 5, "previous_driver_id": None}
        )
        self.assertEqual(reassigned["action_type"], "reassigned")
        self.assertEqual(assigned["action_type"], "assigned")

    def test_item_add_exposes_is_replaced(self):
        details = {"product_id": 1, "quantity": "2", "replaced": True}
        result = LogDetailsFormatter.format(OperationType.ITEM_ADD, details)
        self.assertEqual(result, {"product_id": 1, "quantity": "2", "is_replaced": True})

    def test_fact_enter_is_formatted(self):
        details = {
            "stage_id": 7, "product_id": 1,
            "document_quantity": "10", "actual_quantity": "9", "comment": None,
        }
        result = LogDetailsFormatter.format(OperationType.FACT_ENTER, details)
        self.assertEqual(result["actual_quantity"], "9")
        self.assertIsNone(result["comment"])

    def test_every_operation_has_handler_or_is_default_only(self):
        """Новая операция без обработчика должна попадать в DEFAULT_ONLY осознанно."""
        for operation in OperationType:
            if operation in DEFAULT_ONLY:
                continue
            probe = LogDetailsFormatter.format(operation, {"__probe__": 1})
            self.assertNotEqual(
                probe, {"__probe__": 1},
                f"{operation.name}: нет обработчика в LogDetailsFormatter.format",
            )

    def test_none_details_stay_none(self):
        self.assertIsNone(LogDetailsFormatter.format(OperationType.ITEM_ADD, None))


if __name__ == "__main__":
    unittest.main()
