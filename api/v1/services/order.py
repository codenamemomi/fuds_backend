from sqlalchemy.orm import Session

from api.v1.models.order import Order
from api.v1.schema.order import OrderCreate, OrderRead
from api.v1.services.base import BaseService


class OrderService(BaseService[Order, OrderCreate, OrderRead]):
    def __init__(self, db: Session):
        super().__init__(Order, db)
