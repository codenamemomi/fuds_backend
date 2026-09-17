from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from api.v1.models.categories import GROCERY_AISLES, grocery_aisle_keys, vendor_categories_for_group
from api.v1.models.marketplace import GrocerySubscription, MarketplaceFrequency, MarketplaceProduct
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
    MarketplaceProductRead,
)
from api.v1.services.order import OrderService

LAGOS_TZ = ZoneInfo("Africa/Lagos")
GROCERY_DELIVERY_HOUR = 10


class MarketplaceService:
    def __init__(self, db: Session):
        self.db = db

    def catalog(self, aisle: str | None = None, search: str | None = None) -> GroceryCatalogRead:
        query = self.db.query(MarketplaceProduct).filter(MarketplaceProduct.is_active.is_(True))
        if aisle:
            if aisle not in grocery_aisle_keys():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown grocery aisle '{aisle}'",
                )
            query = query.filter(MarketplaceProduct.aisle == aisle)
        if search and search.strip():
            query = query.filter(MarketplaceProduct.name.ilike(f"%{search.strip()}%"))

        products = query.order_by(MarketplaceProduct.aisle.asc(), MarketplaceProduct.name.asc()).all()
        counts: dict[str, int] = {}
        reads: list[MarketplaceProductRead] = []
        for product in products:
            reads.append(_marketplace_product_read(product))
            if product.aisle:
                counts[product.aisle] = counts.get(product.aisle, 0) + 1

        # Aisle counts should reflect the full grocery catalog, not the filtered list
        if aisle or (search and search.strip()):
            rows = self.db.query(MarketplaceProduct.aisle).filter(
                MarketplaceProduct.is_active.is_(True), MarketplaceProduct.aisle.isnot(None)
            ).all()
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
        existing = self.db.query(GrocerySubscription).filter(
            GrocerySubscription.user_id == user_id,
            GrocerySubscription.status != "cancelled",
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a grocery subscription. Edit the existing list instead.",
            )
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
            change_summary=None,
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
            previous_items = row.items or []
            packed, names = self._pack_items(payload.items)
            row.items = packed
            row.item_list = names
            row.change_summary = self._build_change_summary(previous_items, packed)
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
        if row.order_id:
            order = self.db.query(Order).filter(Order.id == row.order_id).first()
            if order and order.status not in {"completed", "cancelled"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This subscription has a pending grocery delivery and cannot be deleted yet.",
                )
        row.status = "cancelled"
        self.db.commit()

    def checkout(self, user_id: int, sub_id: int, cycles: int = 1):
        row = self._owned(user_id, sub_id)
        if row.order_id:
            existing = self.db.query(Order).filter(
                Order.id == row.order_id,
                Order.user_id == user_id,
                Order.parent_order_id.is_(None),
            ).first()
            if existing:
                if existing.payment_status != "paid":
                    return OrderService(self.db)._serialize_order(existing)
                if existing.status not in {"completed", "cancelled"}:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This grocery delivery is already paid. You can pay again after it is delivered.",
                    )
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

        if all(item.marketplace_product_id for item in items):
            grand = round(sum(item.subtotal for item in items) * cycles, 2)
            for item in items:
                self.db.add(
                    OrderItem(
                        order_id=parent.id,
                        vendor_id=None,
                        product_id=None,
                        marketplace_product_id=item.marketplace_product_id,
                        quantity=item.quantity,
                        price=item.price,
                    )
                )
            parent.total_price = grand
            row.order_id = parent.id
            self.db.commit()
            self.db.refresh(parent)
            return OrderService(self.db)._serialize_order(parent)

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
            product = self.db.query(MarketplaceProduct).filter(
                MarketplaceProduct.id == item.product_id,
                MarketplaceProduct.is_active.is_(True),
            ).first()
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
        marketplace_products = {
            p.id: p for p in self.db.query(MarketplaceProduct).filter(
                MarketplaceProduct.id.in_(ids), MarketplaceProduct.is_active.is_(True)
            ).all()
        } if ids else {}
        missing_ids = [product_id for product_id in ids if product_id not in marketplace_products]
        legacy_products = {
            p.id: p for p in self.db.query(Product).options(joinedload(Product.vendor)).filter(
                Product.id.in_(missing_ids)
            ).all()
        } if missing_ids else {}
        result: list[GroceryItemRead] = []
        for entry in raw:
            product_id = int(entry["product_id"])
            product = marketplace_products.get(product_id) or legacy_products.get(product_id)
            if not product:
                continue
            qty = int(entry.get("quantity") or 1)
            price = float(product.price)
            if isinstance(product, MarketplaceProduct):
                result.append(GroceryItemRead(
                    product_id=product.id,
                    quantity=qty,
                    name=product.name,
                    price=price,
                    subtotal=round(price * qty, 2),
                    aisle=product.aisle,
                    image_url=product.image_url,
                    marketplace_product_id=product.id,
                ))
            else:
                result.append(GroceryItemRead(
                    product_id=product.id,
                    quantity=qty,
                    name=product.name,
                    price=price,
                    subtotal=round(price * qty, 2),
                    aisle=product.aisle,
                    image_url=product.image_url,
                    vendor_id=product.vendor_id,
                    vendor_name=product.vendor.business_name if product.vendor else None,
                ))
        return result

    def _to_read(self, row: GrocerySubscription) -> GrocerySubscriptionRead:
        items = self._hydrate_items(row)
        total = round(sum(i.subtotal for i in items), 2)
        payment_status = None
        if row.order_id:
            order_state = self.db.query(Order.status, Order.payment_status).filter(Order.id == row.order_id).first()
            if order_state and order_state[0] not in {"completed", "cancelled"}:
                payment_status = order_state[1]
        changes = row.change_summary or {}
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
            payment_status=payment_status,
            added_items=changes.get("added", []),
            removed_items=changes.get("removed", []),
            change_total=float(changes.get("change_total", 0) or 0),
        )

    def _build_change_summary(self, previous: list[dict], current: list[dict]) -> dict:
        before = {int(item["product_id"]): int(item.get("quantity") or 1) for item in previous}
        after = {int(item["product_id"]): int(item.get("quantity") or 1) for item in current}
        ids = set(before) | set(after)
        products = {
            product.id: product
            for product in self.db.query(MarketplaceProduct).filter(MarketplaceProduct.id.in_(ids)).all()
        } if ids else {}
        added: list[dict] = []
        removed: list[dict] = []
        change_total = 0.0
        for product_id in ids:
            delta = after.get(product_id, 0) - before.get(product_id, 0)
            product = products.get(product_id)
            if not delta or not product:
                continue
            amount = round(abs(delta) * float(product.price), 2)
            entry = {
                "product_id": product_id,
                "name": product.name,
                "quantity": abs(delta),
                "amount": amount,
            }
            (added if delta > 0 else removed).append(entry)
            change_total += amount if delta > 0 else -amount
        return {"added": added, "removed": removed, "change_total": round(change_total, 2)}


def _marketplace_product_read(product: MarketplaceProduct) -> MarketplaceProductRead:
    return MarketplaceProductRead(
        name=product.name,
        price=float(product.price),
        category=product.category,
        aisle=product.aisle,
        image_url=product.image_url,
        id=product.id,
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
