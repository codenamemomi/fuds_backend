from sqlalchemy.orm import Session

from api.v1.models.vendor import Vendor, VendorStatus
from api.v1.schema.vendor import VendorCreate, VendorRead
from api.v1.services.base import BaseService
from api.utils.cache import invalidate_vendor


class VendorService(BaseService[Vendor, VendorCreate, VendorRead]):
    def __init__(self, db: Session):
        super().__init__(Vendor, db)

    def create(self, payload: VendorCreate, commit: bool = True) -> Vendor:
        """Create a vendor and invalidate browse cache."""
        vendor = super().create(payload, commit=commit)
        if commit:
            invalidate_vendor(vendor.id)
        return vendor

    def update_status(self, vendor_id: int, status: VendorStatus) -> Vendor | None:
        """Update vendor activation status and invalidate cache."""
        vendor = self.get_by_id(vendor_id)
        if vendor:
            vendor.status = status
            self.db.commit()
            self.db.refresh(vendor)
            invalidate_vendor(vendor_id)
        return vendor

    def update_vendor(self, vendor_id: int, updates: dict) -> Vendor | None:
        """Partially update vendor fields and invalidate cache."""
        vendor = self.get_by_id(vendor_id)
        if vendor:
            for key, value in updates.items():
                if hasattr(vendor, key):
                    setattr(vendor, key, value)
            self.db.commit()
            self.db.refresh(vendor)
            invalidate_vendor(vendor_id)
        return vendor

    def delete_vendor(self, vendor_id: int) -> bool:
        """Delete a vendor and invalidate its cache."""
        vendor = self.get_by_id(vendor_id)
        if vendor:
            self.db.delete(vendor)
            self.db.commit()
            invalidate_vendor(vendor_id)
            return True
        return False
