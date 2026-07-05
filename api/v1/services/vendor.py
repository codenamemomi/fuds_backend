from sqlalchemy.orm import Session

from api.v1.models.vendor import Vendor
from api.v1.schema.vendor import VendorCreate, VendorRead
from api.v1.services.base import BaseService


class VendorService(BaseService[Vendor, VendorCreate, VendorRead]):
    def __init__(self, db: Session):
        super().__init__(Vendor, db)
