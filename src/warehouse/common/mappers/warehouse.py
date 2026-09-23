from warehouse.common.dto import StockItemDTO, WarehouseDTO
from warehouse.dal.entities import StockOnWarehouse, Warehouse


def to_warehouse(w: Warehouse) -> WarehouseDTO:
    return WarehouseDTO(id=w.id, title=w.title, address=w.address)


def to_stock_item(s: StockOnWarehouse) -> StockItemDTO:
    return StockItemDTO(
        warehouse_id=s.warehouse_id,
        product_id=s.product_id,
        article_number=s.product.article_number,
        product_name=s.product.product_name,
        measurement_name=s.product.measurement.measurement_name,
        quantity=s.quantity,
        reserved_quantity=s.reserved_quantity,
    )
