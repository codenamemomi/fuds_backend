from sqlalchemy.orm import Session

from api.v1.models.product import Product
from api.v1.schema.product import ProductCreate, ProductRead
from api.v1.services.base import BaseService
from api.utils.cache import invalidate_product


class ProductService(BaseService[Product, ProductCreate, ProductRead]):
    def __init__(self, db: Session):
        super().__init__(Product, db)

    def create(self, payload: ProductCreate, commit: bool = True) -> Product:
        """Create a product and invalidate browse cache."""
        product = super().create(payload, commit=commit)
        if commit:
            invalidate_product(product.id, vendor_id=product.vendor_id)
        return product

    def update_product(self, product_id: int, updates: dict) -> Product | None:
        """Partially update product fields and invalidate cache."""
        product = self.get_by_id(product_id)
        if product:
            vendor_id = product.vendor_id
            for key, value in updates.items():
                if hasattr(product, key):
                    setattr(product, key, value)
            self.db.commit()
            self.db.refresh(product)
            invalidate_product(product_id, vendor_id=vendor_id)
        return product

    def delete_product(self, product_id: int) -> bool:
        """Delete a product and invalidate its cache."""
        product = self.get_by_id(product_id)
        if product:
            vendor_id = product.vendor_id
            self.db.delete(product)
            self.db.commit()
            invalidate_product(product_id, vendor_id=vendor_id)
            return True
        return False
