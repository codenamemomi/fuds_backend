from sqlalchemy.orm import Session

from api.v1.models.marketplace import Marketplace
from api.v1.schema.marketplace import MarketplaceCreate, MarketplaceRead
from api.v1.services.base import BaseService


class MarketplaceService(BaseService[Marketplace, MarketplaceCreate, MarketplaceRead]):
    def __init__(self, db: Session):
        super().__init__(Marketplace, db)
