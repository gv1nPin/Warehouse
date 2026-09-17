from sqlalchemy import select
from sqlalchemy.orm import joinedload

from Warehouse.api.dto import ProductDTO
from Warehouse.dal.entities import Product
from Warehouse.api.mappers import to_product
from .base_repository import BaseRepository


class ProductRepository(BaseRepository[Product]):
    model = Product

    def _select(self):
        return (
            select(Product)
            .options(joinedload(Product.measurement, innerjoin=True))
            .where(Product.is_deleted.is_(False))
        )

    def get_by_id(self, product_id: int) -> ProductDTO | None:
        p = self._one(self._select().where(Product.id == product_id))
        return to_product(p) if p else None

    def get_by_article(self, article_number: str) -> ProductDTO | None:
        p = self._one(self._select().where(Product.article_number == article_number))
        return to_product(p) if p else None

    def list_active(self) -> list[ProductDTO]:
        stmt = self._select().order_by(Product.product_name)
        return [to_product(p) for p in self._all(stmt)]

    def create(self, article_number: str, product_name: str, measurement_id: int) -> int:
        p = Product(
            article_number=article_number,
            product_name=product_name,
            measurement_id=measurement_id,
        )
        return self._add(p).id

    def soft_delete(self, product_id: int) -> bool:
        return self._update(product_id, is_deleted=True)
