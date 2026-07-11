#!/usr/bin/env python3
"""
FUDS Database Seed Script
--------------------------
Populates the database with realistic Nigerian restaurant, grocery, bakery,
and supermarket vendors along with ~35 products.

Usage:
    python scripts/seed_db.py

Idempotent: skips vendors/products that already exist by business_name/product name+vendor.
"""
import sys
from datetime import time
from pathlib import Path

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.db.session import SessionLocal
from api.v1.models.vendor import Vendor, VendorCategory, VendorStatus
from api.v1.models.product import Product, ProductCategory


VENDORS = [
    {
        "business_name": "Mama Titi's Kitchen",
        "category": VendorCategory.RESTAURANT,
        "business_description": "Authentic Lagos home-cooking. Jollof rice, egusi, eba, and more.",
        "address": "14 Bode Thomas Street, Surulere, Lagos",
        "opening_time": time(8, 0),
        "closing_time": time(22, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Jollof Rice + Chicken", "price": 2500.00, "category": ProductCategory.RESTAURANT},
            {"name": "Egusi Soup + Eba", "price": 2000.00, "category": ProductCategory.RESTAURANT},
            {"name": "Fried Rice + Plantain", "price": 2800.00, "category": ProductCategory.RESTAURANT},
            {"name": "Pounded Yam + Oha Soup", "price": 3000.00, "category": ProductCategory.RESTAURANT},
            {"name": "Moi Moi (2 wraps)", "price": 800.00, "category": ProductCategory.RESTAURANT},
            {"name": "Pepper Soup (Catfish)", "price": 3500.00, "category": ProductCategory.RESTAURANT},
            {"name": "Chapman (Large)", "price": 1200.00, "category": ProductCategory.RESTAURANT},
        ],
    },
    {
        "business_name": "Alhaji Suya Spot",
        "category": VendorCategory.RESTAURANT,
        "business_description": "The best suya in Lagos. Grilled to perfection with our secret spice blend.",
        "address": "7 Allen Avenue, Ikeja, Lagos",
        "opening_time": time(16, 0),
        "closing_time": time(23, 59),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Beef Suya (200g)", "price": 2000.00, "category": ProductCategory.RESTAURANT},
            {"name": "Chicken Suya (full)", "price": 3500.00, "category": ProductCategory.RESTAURANT},
            {"name": "Gizzard Suya", "price": 2500.00, "category": ProductCategory.RESTAURANT},
            {"name": "Kidney Suya", "price": 2200.00, "category": ProductCategory.RESTAURANT},
            {"name": "Suya Wrap (2pcs)", "price": 1800.00, "category": ProductCategory.RESTAURANT},
            {"name": "Kunu (500ml)", "price": 600.00, "category": ProductCategory.RESTAURANT},
        ],
    },
    {
        "business_name": "Lekki Fresh Farms",
        "category": VendorCategory.GROCERY_STORE,
        "business_description": "Fresh farm produce delivered from the source. Vegetables, tubers, and grains.",
        "address": "Admiralty Way, Lekki Phase 1, Lagos",
        "opening_time": time(7, 0),
        "closing_time": time(20, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Tomatoes (1kg)", "price": 1500.00, "category": ProductCategory.GROCERY_STORE},
            {"name": "Red Onions (1kg)", "price": 900.00, "category": ProductCategory.GROCERY_STORE},
            {"name": "Yam (medium tuber)", "price": 2500.00, "category": ProductCategory.GROCERY_STORE},
            {"name": "Ugu (Fluted Pumpkin) Bunch", "price": 500.00, "category": ProductCategory.GROCERY_STORE},
            {"name": "Plantain (bunch of 10)", "price": 2000.00, "category": ProductCategory.GROCERY_STORE},
            {"name": "Scotch Bonnet Pepper (500g)", "price": 1200.00, "category": ProductCategory.GROCERY_STORE},
            {"name": "Garlic (200g)", "price": 800.00, "category": ProductCategory.GROCERY_STORE},
            {"name": "Ginger (200g)", "price": 600.00, "category": ProductCategory.GROCERY_STORE},
        ],
    },
    {
        "business_name": "Golden Crust Bakery",
        "category": VendorCategory.BAKERY,
        "business_description": "Freshly baked breads, cakes, and pastries for every occasion.",
        "address": "22 Awolowo Road, Ikoyi, Lagos",
        "opening_time": time(6, 30),
        "closing_time": time(19, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Agege Bread (Large)", "price": 1200.00, "category": ProductCategory.BAKERY},
            {"name": "Meat Pie (2pcs)", "price": 1000.00, "category": ProductCategory.BAKERY},
            {"name": "Egg Roll (4pcs)", "price": 800.00, "category": ProductCategory.BAKERY},
            {"name": "Chin Chin (500g)", "price": 1500.00, "category": ProductCategory.BAKERY},
            {"name": "Puff Puff (10pcs)", "price": 600.00, "category": ProductCategory.BAKERY},
            {"name": "Sausage Roll (4pcs)", "price": 900.00, "category": ProductCategory.BAKERY},
            {"name": "Birthday Cake (1kg)", "price": 12000.00, "category": ProductCategory.BAKERY},
        ],
    },
    {
        "business_name": "MartPlus Supermarket",
        "category": VendorCategory.SUPERMARKET,
        "business_description": "Your one-stop shop for household essentials, packaged foods, and beverages.",
        "address": "Palms Shopping Mall, Lekki, Lagos",
        "opening_time": time(9, 0),
        "closing_time": time(21, 0),
        "status": VendorStatus.ACTIVATED,
        "products": [
            {"name": "Dangote Sugar (1kg)", "price": 1800.00, "category": ProductCategory.SUPERMARKET},
            {"name": "Golden Penny Semolina (2kg)", "price": 3500.00, "category": ProductCategory.SUPERMARKET},
            {"name": "Peak Milk Tin (170g)", "price": 900.00, "category": ProductCategory.SUPERMARKET},
            {"name": "Indomie Chicken (10 packs)", "price": 3000.00, "category": ProductCategory.SUPERMARKET},
            {"name": "Coca-Cola (50cl, 6-pack)", "price": 3600.00, "category": ProductCategory.SUPERMARKET},
            {"name": "Groundnut Oil (5L)", "price": 9500.00, "category": ProductCategory.SUPERMARKET},
            {"name": "Detol Soap (3-pack)", "price": 2100.00, "category": ProductCategory.SUPERMARKET},
        ],
    },
]


def seed():
    db = SessionLocal()
    try:
        vendors_added = 0
        products_added = 0

        for vendor_data in VENDORS:
            products = vendor_data.pop("products")

            # Check if vendor already exists
            existing = db.query(Vendor).filter(
                Vendor.business_name == vendor_data["business_name"]
            ).first()

            if existing:
                print(f"  [SKIP] Vendor already exists: {vendor_data['business_name']}")
                vendor = existing
            else:
                vendor = Vendor(**vendor_data)
                db.add(vendor)
                db.flush()  # get vendor.id
                vendors_added += 1
                print(f"  [ADD]  Vendor: {vendor_data['business_name']}")

            for p in products:
                existing_product = db.query(Product).filter(
                    Product.vendor_id == vendor.id,
                    Product.name == p["name"],
                ).first()

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
