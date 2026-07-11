import json
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.utils.redis_utils import redis_client
from api.v1.models.product import Product
from api.v1.schema.cart import CartItemCreate, CartItemRead, CartItemUpdate, CartRead

CART_TTL = 60 * 60 * 24 * 3  # 3 days


def _cart_key(user_id: int) -> str:
    return f"cart:{user_id}"


class CartService:
    def __init__(self, db: Session):
        self.db = db

    def _load_raw(self, user_id: int) -> dict[str, dict]:
        """Load raw cart dict from Redis: {product_id_str: {vendor_id, quantity}}"""
        raw = redis_client.get(_cart_key(user_id))
        if not raw:
            return {}
        return json.loads(raw)

    def _save_raw(self, user_id: int, data: dict) -> None:
        redis_client.setex(_cart_key(user_id), CART_TTL, json.dumps(data))

    def add_item(self, user_id: int, item: CartItemCreate) -> CartRead:
        cart = self._load_raw(user_id)
        key = str(item.product_id)

        # Validate product exists
        product = self.db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        if product.vendor_id != item.vendor_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product does not belong to this vendor")

        if key in cart:
            cart[key]["quantity"] += item.quantity
        else:
            cart[key] = {"vendor_id": item.vendor_id, "quantity": item.quantity}

        self._save_raw(user_id, cart)
        return self.get_cart(user_id)

    def get_cart(self, user_id: int) -> CartRead:
        cart = self._load_raw(user_id)
        if not cart:
            return CartRead(user_id=user_id, items=[], total=0.0, item_count=0)

        product_ids = [int(pid) for pid in cart.keys()]
        products = {
            p.id: p
            for p in self.db.query(Product).filter(Product.id.in_(product_ids)).all()
        }

        items: list[CartItemRead] = []
        total = 0.0
        for pid_str, meta in cart.items():
            pid = int(pid_str)
            product = products.get(pid)
            if not product:
                continue
            qty = meta["quantity"]
            price = float(product.price)
            subtotal = price * qty
            total += subtotal
            items.append(CartItemRead(
                product_id=pid,
                vendor_id=meta["vendor_id"],
                name=product.name,
                price=price,
                quantity=qty,
                subtotal=subtotal,
                image_url=product.image_url,
            ))

        return CartRead(user_id=user_id, items=items, total=round(total, 2), item_count=len(items))

    def update_item(self, user_id: int, update: CartItemUpdate) -> CartRead:
        cart = self._load_raw(user_id)
        key = str(update.product_id)
        if key not in cart:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart")

        if update.quantity == 0:
            del cart[key]
        else:
            cart[key]["quantity"] = update.quantity

        self._save_raw(user_id, cart)
        return self.get_cart(user_id)

    def remove_item(self, user_id: int, product_id: int) -> CartRead:
        cart = self._load_raw(user_id)
        key = str(product_id)
        if key not in cart:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart")
        del cart[key]
        self._save_raw(user_id, cart)
        return self.get_cart(user_id)

    def clear_cart(self, user_id: int) -> None:
        redis_client.delete(_cart_key(user_id))
