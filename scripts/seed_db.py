#!/usr/bin/env python3
"""
FUDS Database Seed Script
--------------------------
Populates the database with Lagos vendors across all browse groups:
  food (restaurant, bakery), grocery (grocery_store, supermarket, local_market),
  shops, pharmacy, packages.

Usage:
    python scripts/seed_db.py

Idempotent: skips vendors/products that already exist by business_name/product name+vendor.
"""
import copy
import sys
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.db.session import SessionLocal
from api.v1.models.categories import ProductCategory, VendorCategory
from api.v1.models.product import Product
from api.v1.models.vendor import Vendor, VendorStatus

VC = VendorCategory
PC = ProductCategory

VENDORS = [
    # ── Food ──────────────────────────────────────────────────────────────────
    {
        "business_name": "Mama Titi's Kitchen",
        "category": VC.RESTAURANT.value,
        "business_description": "Authentic Lagos home-cooking. Jollof rice, egusi, eba, and more.",
        "address": "14 Bode Thomas Street, Surulere, Lagos",
        "opening_time": time(8, 0),
        "closing_time": time(22, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Jollof Rice + Chicken", "price": 2500.00, "category": PC.RESTAURANT.value},
            {"name": "Egusi Soup + Eba", "price": 2000.00, "category": PC.RESTAURANT.value},
            {"name": "Fried Rice + Plantain", "price": 2800.00, "category": PC.RESTAURANT.value},
            {"name": "Pounded Yam + Oha Soup", "price": 3000.00, "category": PC.RESTAURANT.value},
            {"name": "Moi Moi (2 wraps)", "price": 800.00, "category": PC.RESTAURANT.value},
            {"name": "Pepper Soup (Catfish)", "price": 3500.00, "category": PC.RESTAURANT.value},
            {"name": "Chapman (Large)", "price": 1200.00, "category": PC.RESTAURANT.value},
        ],
    },
    {
        "business_name": "Alhaji Suya Spot",
        "category": VC.RESTAURANT.value,
        "business_description": "The best suya in Lagos. Grilled to perfection with our secret spice blend.",
        "address": "7 Allen Avenue, Ikeja, Lagos",
        "opening_time": time(16, 0),
        "closing_time": time(23, 59),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Beef Suya (200g)", "price": 2000.00, "category": PC.RESTAURANT.value},
            {"name": "Chicken Suya (full)", "price": 3500.00, "category": PC.RESTAURANT.value},
            {"name": "Gizzard Suya", "price": 2500.00, "category": PC.RESTAURANT.value},
            {"name": "Suya Wrap (2pcs)", "price": 1800.00, "category": PC.RESTAURANT.value},
            {"name": "Kunu (500ml)", "price": 600.00, "category": PC.RESTAURANT.value},
        ],
    },
    {
        "business_name": "Golden Crust Bakery",
        "category": VC.BAKERY.value,
        "business_description": "Freshly baked breads, cakes, and pastries for every occasion.",
        "address": "22 Awolowo Road, Ikoyi, Lagos",
        "opening_time": time(6, 30),
        "closing_time": time(19, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Agege Bread (Large)", "price": 1200.00, "category": PC.BAKERY.value},
            {"name": "Meat Pie (2pcs)", "price": 1000.00, "category": PC.BAKERY.value},
            {"name": "Puff Puff (10pcs)", "price": 600.00, "category": PC.BAKERY.value},
            {"name": "Birthday Cake (1kg)", "price": 12000.00, "category": PC.BAKERY.value},
        ],
    },
    # ── Grocery ───────────────────────────────────────────────────────────────
    {
        "business_name": "Lekki Fresh Farms",
        "category": VC.GROCERY_STORE.value,
        "business_description": "Fresh farm produce delivered from the source. Vegetables, tubers, and grains.",
        "address": "Admiralty Way, Lekki Phase 1, Lagos",
        "opening_time": time(7, 0),
        "closing_time": time(20, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Tomatoes (1kg)", "price": 1500.00, "category": PC.GROCERY_STORE.value},
            {"name": "Yam (medium tuber)", "price": 2500.00, "category": PC.GROCERY_STORE.value},
            {"name": "Plantain (bunch of 10)", "price": 2000.00, "category": PC.GROCERY_STORE.value},
            {"name": "Ugu Bunch", "price": 500.00, "category": PC.GROCERY_STORE.value},
        ],
    },
    {
        "business_name": "MartPlus Supermarket",
        "category": VC.SUPERMARKET.value,
        "business_description": "Your one-stop shop for household essentials, packaged foods, and beverages.",
        "address": "Palms Shopping Mall, Lekki, Lagos",
        "opening_time": time(9, 0),
        "closing_time": time(21, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Dangote Sugar (1kg)", "price": 1800.00, "category": PC.SUPERMARKET.value},
            {"name": "Indomie Chicken (10 packs)", "price": 3000.00, "category": PC.SUPERMARKET.value},
            {"name": "Groundnut Oil (5L)", "price": 9500.00, "category": PC.SUPERMARKET.value},
            {"name": "Peak Milk Tin (170g)", "price": 900.00, "category": PC.SUPERMARKET.value},
        ],
    },
    {
        "business_name": "Balogun Market Hub",
        "category": VC.LOCAL_MARKET.value,
        "business_description": "Traditional market staples — spices, dry goods, and local ingredients.",
        "address": "Balogun Market, Lagos Island",
        "opening_time": time(7, 0),
        "closing_time": time(18, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Crayfish (cup)", "price": 800.00, "category": PC.LOCAL_MARKET.value},
            {"name": "Palm Oil (1L)", "price": 2200.00, "category": PC.LOCAL_MARKET.value},
            {"name": "Locust Beans (Iru)", "price": 500.00, "category": PC.LOCAL_MARKET.value},
            {"name": "Stockfish (medium)", "price": 4500.00, "category": PC.LOCAL_MARKET.value},
        ],
    },
    # ── Shops ─────────────────────────────────────────────────────────────────
    {
        "business_name": "City Essentials Shop",
        "category": VC.SHOP.value,
        "business_description": "Convenience retail — toiletries, snacks, and everyday items.",
        "address": "15 Admiralty Way, Lekki, Lagos",
        "opening_time": time(8, 0),
        "closing_time": time(22, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Tissue Pack (6 rolls)", "price": 2500.00, "category": PC.SHOP.value},
            {"name": "Toothpaste (120g)", "price": 1200.00, "category": PC.SHOP.value},
            {"name": "Airtime Bundle Card", "price": 1000.00, "category": PC.SHOP.value},
        ],
    },
    # ── Pharmacy ──────────────────────────────────────────────────────────────
    {
        "business_name": "MedPlus Pharmacy Lekki",
        "category": VC.PHARMACY.value,
        "business_description": "Licensed pharmacy for OTC meds, first aid, and wellness products.",
        "address": "Plot 5 Admiralty Way, Lekki Phase 1, Lagos",
        "opening_time": time(8, 0),
        "closing_time": time(21, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Paracetamol (20 tabs)", "price": 600.00, "category": PC.PHARMACY.value},
            {"name": "Vitamin C (1000mg)", "price": 3500.00, "category": PC.PHARMACY.value},
            {"name": "Hand Sanitizer (500ml)", "price": 1800.00, "category": PC.PHARMACY.value},
            {"name": "First Aid Kit (basic)", "price": 7500.00, "category": PC.PHARMACY.value},
        ],
    },
    # ── Packages ──────────────────────────────────────────────────────────────
    {
        "business_name": "FUDS Express Courier",
        "category": VC.PACKAGE_DELIVERY.value,
        "business_description": "Same-day package delivery across Lagos Island, Mainland, and Lekki.",
        "address": "Victoria Island Hub, Lagos",
        "opening_time": time(7, 0),
        "closing_time": time(20, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Document Envelope (same-day)", "price": 2500.00, "category": PC.PACKAGE_DELIVERY.value},
            {"name": "Small Parcel (under 5kg)", "price": 4500.00, "category": PC.PACKAGE_DELIVERY.value},
            {"name": "Medium Parcel (5–15kg)", "price": 7500.00, "category": PC.PACKAGE_DELIVERY.value},
        ],
    },
]


def seed():
    db = SessionLocal()
    try:
        vendors_added = 0
        products_added = 0

        for raw in VENDORS:
            vendor_data = copy.deepcopy(raw)
            products = vendor_data.pop("products")

            existing = (
                db.query(Vendor)
                .filter(Vendor.business_name == vendor_data["business_name"])
                .first()
            )

            if existing:
                print(f"  [SKIP] Vendor already exists: {vendor_data['business_name']}")
                vendor = existing
                # Keep category up to date if we expanded taxonomy
                if existing.category != vendor_data.get("category"):
                    existing.category = vendor_data.get("category")
            else:
                vendor = Vendor(**vendor_data)
                db.add(vendor)
                db.flush()
                vendors_added += 1
                print(f"  [ADD]  Vendor: {vendor_data['business_name']} ({vendor_data['category']})")

            for p in products:
                existing_product = (
                    db.query(Product)
                    .filter(Product.vendor_id == vendor.id, Product.name == p["name"])
                    .first()
                )
                if existing_product:
                    print(f"         [SKIP] Product: {p['name']}")
                else:
                    product = Product(vendor_id=vendor.id, **p)
                    db.add(product)
                    products_added += 1
                    print(f"         [ADD]  Product: {p['name']} — ₦{p['price']:,.2f}")

        db.commit()
        print(f"\n✅ Seed complete: {vendors_added} vendors, {products_added} products added.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding FUDS database...\n")
    seed()
