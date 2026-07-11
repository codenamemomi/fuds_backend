from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.v1.models.order import Order
from api.v1.models.order_item import OrderItem
from api.v1.schema.order import CheckoutRequest, OrderItemRead, OrderRead
from api.v1.services.cart import CartService


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def checkout(self, user_id: int, request: CheckoutRequest) -> OrderRead:
        cart_service = CartService(self.db)
        cart = cart_service.get_cart(user_id)

        if not cart.items:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        # Group items by vendor
        vendor_groups: dict[int, list] = {}
        for item in cart.items:
            vendor_groups.setdefault(item.vendor_id, []).append(item)

        # Create parent order (umbrella for all vendors)
        parent_order = Order(
            user_id=user_id,
            status="pending",
            payment_status="pending",
            total_price=cart.total,
            delivery_time=request.delivery_time,
            created_at=datetime.utcnow(),
        )
        self.db.add(parent_order)
        self.db.flush()  # get parent_order.id without committing

        # Create one sub-order per vendor
        for vendor_id, vendor_items in vendor_groups.items():
            vendor_total = sum(i.price * i.quantity for i in vendor_items)
            sub_order = Order(
                user_id=user_id,
                parent_order_id=parent_order.id,
                vendor_id=vendor_id,
                status="pending",
                payment_status="pending",
                total_price=round(vendor_total, 2),
                delivery_time=request.delivery_time,
                created_at=datetime.utcnow(),
            )
            self.db.add(sub_order)
            self.db.flush()

            for item in vendor_items:
                order_item = OrderItem(
                    order_id=sub_order.id,
                    vendor_id=vendor_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    price=item.price,
                )
                self.db.add(order_item)

        self.db.commit()
        self.db.refresh(parent_order)

        # Clear cart after successful checkout
        cart_service.clear_cart(user_id)

        return self._serialize_order(parent_order)

    def list_orders(self, user_id: int) -> list[OrderRead]:
        # Return only top-level (parent) orders for the user
        orders = (
            self.db.query(Order)
            .filter(Order.user_id == user_id, Order.parent_order_id.is_(None))
            .order_by(Order.created_at.desc())
            .all()
        )
        return [self._serialize_order(o) for o in orders]

    def get_order(self, order_id: int, user_id: int) -> OrderRead:
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.user_id == user_id)
            .first()
        )
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return self._serialize_order(order)

    def _serialize_order(self, order: Order) -> OrderRead:
        items = []
        # For parent orders, collect items from all sub-orders
        sub_orders = order.sub_orders if order.sub_orders else []
        all_item_rows = list(order.items)
        for sub in sub_orders:
            all_item_rows.extend(sub.items)

        for oi in all_item_rows:
            items.append(OrderItemRead(
                id=oi.id,
                product_id=oi.product_id,
                vendor_id=oi.vendor_id,
                quantity=oi.quantity,
                price=float(oi.price),
                product_name=oi.product.name if oi.product else None,
                vendor_name=oi.vendor.business_name if oi.vendor else None,
            ))

        return OrderRead(
            id=order.id,
            user_id=order.user_id,
            parent_order_id=order.parent_order_id,
            vendor_id=order.vendor_id,
            status=order.status,
            delivery_time=order.delivery_time,
            payment_status=order.payment_status,
            total_price=float(order.total_price),
            created_at=order.created_at,
            completed_at=order.completed_at,
            items=items,
        )
