from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductDTO:
    id: int
    article_number: str
    product_name: str
    measurement_name: str
