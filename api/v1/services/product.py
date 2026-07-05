from sqlalchemy.orm import Session

from api.v1.models.product import Product
from api.v1.schema.product import ProductCreate, ProductRead
from api.v1.services.base import BaseService


class ProductService(BaseService[Product, ProductCreate, ProductRead]):
    def __init__(self, db: Session):
        super().__init__(Product, db)
