import json
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.utils.redis_utils import redis_client
from api.v1.models.product import Product
from api.v1.models.marketplace import MarketplaceProduct
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
        if item.marketplace_product_id is not None:
            product = self.db.query(MarketplaceProduct).filter(
                MarketplaceProduct.id == item.marketplace_product_id,
                MarketplaceProduct.is_active.is_(True),
            ).first()
            key = f"m:{item.marketplace_product_id}"
            if not product:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marketplace product not found")
            metadata = {"marketplace_product_id": item.marketplace_product_id, "vendor_id": None, "quantity": item.quantity}
        else:
            if item.product_id is None or item.vendor_id is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="product_id, vendor_id required for vendor products")
            product = self.db.query(Product).filter(Product.id == item.product_id).first()
            key = f"p:{item.product_id}"
            if not product:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
            if product.vendor_id != item.vendor_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product does not belong to this vendor")
            metadata = {"product_id": item.product_id, "vendor_id": item.vendor_id, "quantity": item.quantity}

        if key in cart:
            cart[key]["quantity"] += item.quantity
        else:
            cart[key] = metadata

        self._save_raw(user_id, cart)
        return self.get_cart(user_id)

    def get_cart(self, user_id: int) -> CartRead:
        cart = self._load_raw(user_id)
        if not cart:
            return CartRead(user_id=user_id, items=[], total=0.0, item_count=0)

        vendor_ids = [int(key[2:]) for key in cart if key.startswith("p:") or key.isdigit()]
        marketplace_ids = [int(key[2:]) for key in cart if key.startswith("m:")]
        products = {
            p.id: p
            for p in self.db.query(Product).filter(Product.id.in_(vendor_ids)).all()
        } if vendor_ids else {}
        marketplace_products = {
            p.id: p
            for p in self.db.query(MarketplaceProduct).filter(MarketplaceProduct.id.in_(marketplace_ids)).all()
        } if marketplace_ids else {}

        items: list[CartItemRead] = []
        total = 0.0
        for key, meta in cart.items():
            is_marketplace = key.startswith("m:")
            pid = int(key[2:]) if ":" in key else int(key)
            product = marketplace_products.get(pid) if is_marketplace else products.get(pid)
            if not product:
                continue
            qty = meta["quantity"]
            price = float(product.price)
            subtotal = price * qty
            total += subtotal
            items.append(CartItemRead(
                product_id=None if is_marketplace else pid,
                marketplace_product_id=pid if is_marketplace else None,
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
        key = f"m:{update.marketplace_product_id}" if update.marketplace_product_id is not None else f"p:{update.product_id}"
        if key not in cart and update.marketplace_product_id is None and update.product_id is not None:
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

    def remove_marketplace_item(self, user_id: int, product_id: int) -> CartRead:
        cart = self._load_raw(user_id)
        key = f"m:{product_id}"
        if key not in cart:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not in cart")
        del cart[key]
        self._save_raw(user_id, cart)
        return self.get_cart(user_id)

    def clear_cart(self, user_id: int) -> None:
        redis_client.delete(_cart_key(user_id))
