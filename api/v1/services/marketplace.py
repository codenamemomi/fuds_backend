from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from api.v1.models.categories import GROCERY_AISLES, grocery_aisle_keys, vendor_categories_for_group
from api.v1.models.marketplace import GrocerySubscription, MarketplaceFrequency
from api.v1.models.order import Order
from api.v1.models.order_item import OrderItem
from api.v1.models.product import Product
from api.v1.schema.marketplace import (
    GroceryAisleRead,
    GroceryCatalogRead,
    GroceryItemIn,
    GroceryItemRead,
    GrocerySubscriptionCreate,
    GrocerySubscriptionRead,
    GrocerySubscriptionUpdate,
)
from api.v1.schema.product import ProductWithVendor
from api.v1.services.order import OrderService

LAGOS_TZ = ZoneInfo("Africa/Lagos")
GROCERY_DELIVERY_HOUR = 10


class MarketplaceService:
    def __init__(self, db: Session):
        self.db = db

    def catalog(self, aisle: str | None = None, search: str | None = None) -> GroceryCatalogRead:
        grocery_cats = vendor_categories_for_group("grocery")
        query = (
            self.db.query(Product)
            .options(joinedload(Product.vendor))
            .filter(Product.category.in_(grocery_cats))
        )
        if aisle:
            if aisle not in grocery_aisle_keys():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown grocery aisle '{aisle}'",
                )
            query = query.filter(Product.aisle == aisle)
        if search and search.strip():
            query = query.filter(Product.name.ilike(f"%{search.strip()}%"))

        products = query.order_by(Product.aisle.asc(), Product.name.asc()).all()
        counts: dict[str, int] = {}
        reads: list[ProductWithVendor] = []
        for product in products:
            reads.append(_product_read(product))
            if product.aisle:
                counts[product.aisle] = counts.get(product.aisle, 0) + 1

        # Aisle counts should reflect the full grocery catalog, not the filtered list
        if aisle or (search and search.strip()):
            rows = (
                self.db.query(Product.aisle)
                .filter(Product.category.in_(grocery_cats), Product.aisle.isnot(None))
                .all()
            )
            counts = {}
            for (key,) in rows:
                if key:
                    counts[str(key)] = counts.get(str(key), 0) + 1

        aisles = [
            GroceryAisleRead(
                key=meta["key"],
                label=meta["label"],
                subtitle=meta["subtitle"],
                icon=meta["icon"],
                product_count=counts.get(meta["key"], 0),
            )
            for meta in GROCERY_AISLES
        ]
        return GroceryCatalogRead(aisles=aisles, products=reads)

    def list_aisles(self) -> list[GroceryAisleRead]:
        return self.catalog().aisles

    def list_subscriptions(self, user_id: int) -> list[GrocerySubscriptionRead]:
        rows = (
            self.db.query(GrocerySubscription)
            .filter(
                GrocerySubscription.user_id == user_id,
                GrocerySubscription.status != "cancelled",
            )
            .order_by(GrocerySubscription.created_at.desc())
            .all()
        )
        return [self._to_read(row) for row in rows]

    def create_subscription(
        self, user_id: int, payload: GrocerySubscriptionCreate
    ) -> GrocerySubscriptionRead:
        packed, names = self._pack_items(payload.items)
        next_dt = _next_delivery_dt(payload.next_delivery)
        row = GrocerySubscription(
            user_id=user_id,
            item_list=names,
            items=packed,
            frequency=payload.frequency.value
            if isinstance(payload.frequency, MarketplaceFrequency)
            else payload.frequency,
            next_delivery=next_dt,
            status="active",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_read(row)

    def update_subscription(
        self, user_id: int, sub_id: int, payload: GrocerySubscriptionUpdate
    ) -> GrocerySubscriptionRead:
        row = self._owned(user_id, sub_id)
        if payload.items is not None:
            packed, names = self._pack_items(payload.items)
            row.items = packed
            row.item_list = names
        if payload.frequency is not None:
            row.frequency = (
                payload.frequency.value
                if isinstance(payload.frequency, MarketplaceFrequency)
                else payload.frequency
            )
        if payload.next_delivery is not None:
            row.next_delivery = _next_delivery_dt(payload.next_delivery)
        if payload.status is not None:
            row.status = payload.status
        self.db.commit()
        return self._to_read(row)

    def cancel_subscription(self, user_id: int, sub_id: int) -> None:
        row = self._owned(user_id, sub_id)
        row.status = "cancelled"
        self.db.commit()

    def checkout(self, user_id: int, sub_id: int):
        row = self._owned(user_id, sub_id)
        items = self._hydrate_items(row)
        if not items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Add grocery items before checkout",
            )

        parent = Order(
            user_id=user_id,
            status="pending",
            payment_status="pending",
            total_price=0,
            delivery_time=row.next_delivery,
            created_at=datetime.utcnow(),
        )
        self.db.add(parent)
        self.db.flush()

        by_vendor: dict[int, list[GroceryItemRead]] = {}
        for item in items:
            if not item.vendor_id:
                continue
            by_vendor.setdefault(item.vendor_id, []).append(item)

        if not by_vendor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Those grocery items are missing vendors",
            )

        grand = 0.0
        for vendor_id, vendor_items in by_vendor.items():
            subtotal = round(sum(i.subtotal for i in vendor_items), 2)
            grand += subtotal
            sub = Order(
                user_id=user_id,
                parent_order_id=parent.id,
                vendor_id=vendor_id,
                status="pending",
                payment_status="pending",
                total_price=subtotal,
                delivery_time=row.next_delivery,
                created_at=datetime.utcnow(),
            )
            self.db.add(sub)
            self.db.flush()
            for item in vendor_items:
                self.db.add(
                    OrderItem(
                        order_id=sub.id,
                        vendor_id=vendor_id,
                        product_id=item.product_id,
                        quantity=item.quantity,
                        price=item.price,
                    )
                )

        parent.total_price = round(grand, 2)
        row.order_id = parent.id
        self.db.commit()
        self.db.refresh(parent)
        return OrderService(self.db)._serialize_order(parent)

    def _pack_items(self, items: list[GroceryItemIn]) -> tuple[list[dict], list[str]]:
        packed: list[dict] = []
        names: list[str] = []
        for item in items:
            product = (
                self.db.query(Product)
                .options(joinedload(Product.vendor))
                .filter(Product.id == item.product_id)
                .first()
            )
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {item.product_id} not found",
                )
            packed.append({"product_id": product.id, "quantity": item.quantity})
            names.append(product.name)
        return packed, names

    def _owned(self, user_id: int, sub_id: int) -> GrocerySubscription:
        row = (
            self.db.query(GrocerySubscription)
            .filter(GrocerySubscription.id == sub_id, GrocerySubscription.user_id == user_id)
            .first()
        )
        if not row or row.status == "cancelled":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roster not found")
        return row

    def _hydrate_items(self, row: GrocerySubscription) -> list[GroceryItemRead]:
        raw = row.items or []
        if not raw and row.item_list:
            return []
        ids = [int(entry["product_id"]) for entry in raw if "product_id" in entry]
        products = {
            p.id: p
            for p in self.db.query(Product)
            .options(joinedload(Product.vendor))
            .filter(Product.id.in_(ids))
            .all()
        } if ids else {}
        result: list[GroceryItemRead] = []
        for entry in raw:
            product = products.get(int(entry["product_id"]))
            if not product:
                continue
            qty = int(entry.get("quantity") or 1)
            price = float(product.price)
            result.append(
                GroceryItemRead(
                    product_id=product.id,
                    quantity=qty,
                    name=product.name,
                    price=price,
                    subtotal=round(price * qty, 2),
                    aisle=product.aisle,
                    image_url=product.image_url,
                    vendor_id=product.vendor_id,
                    vendor_name=product.vendor.business_name if product.vendor else None,
                )
            )
        return result

    def _to_read(self, row: GrocerySubscription) -> GrocerySubscriptionRead:
        items = self._hydrate_items(row)
        total = round(sum(i.subtotal for i in items), 2)
        return GrocerySubscriptionRead(
            id=row.id,
            user_id=row.user_id,
            frequency=_as_frequency(row.frequency),
            next_delivery=row.next_delivery,
            status=row.status,
            order_id=row.order_id,
            created_at=row.created_at,
            items=items,
            item_count=sum(i.quantity for i in items),
            total=total,
        )


def _product_read(product: Product) -> ProductWithVendor:
    vendor = product.vendor
    return ProductWithVendor(
        vendor_id=product.vendor_id,
        name=product.name,
        price=float(product.price),
        category=product.category,
        aisle=product.aisle,
        image_url=product.image_url,
        id=product.id,
        vendor_name=vendor.business_name if vendor else None,
        vendor_category=vendor.category if vendor else None,
        vendor_address=vendor.address if vendor else None,
    )


def _next_delivery_dt(day: date | None) -> datetime:
    today = datetime.now(LAGOS_TZ).date()
    target = day or (today + timedelta(days=1))
    if target < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delivery date cannot be in the past",
        )
    return datetime.combine(target, time(GROCERY_DELIVERY_HOUR, 0))


def _as_frequency(value: MarketplaceFrequency | str) -> MarketplaceFrequency:
    if isinstance(value, MarketplaceFrequency):
        return value
    return MarketplaceFrequency(str(value))
