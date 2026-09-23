from warehouse.common.dto import ProductDTO
from warehouse.dal.entities import Product


def to_product(p: Product) -> ProductDTO:
    return ProductDTO(
        id=p.id,
        article_number=p.article_number,
        product_name=p.product_name,
        measurement_name=p.measurement.measurement_name,
    )
