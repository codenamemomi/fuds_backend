# FUDS Backend

Welcome to the backend repository of **FUDS**, a multi-vendor food delivery and grocery subscription service designed for the Lagos market. This application is powered by FastAPI, SQLAlchemy, PostgreSQL, Redis, and Celery.

---

## 🏗️ Project Architecture & Structure

The codebase is organized into modular layers, separating the routing layer, business logic services, schemas, and models.

```text
fuds_backend/
├── alembic/                # Database migration scripts managed by Alembic
│   └── versions/           # Migration history scripts
├── api/                    # Core backend logic
│   ├── db/                 # DB connection and session configuration
│   │   └── session.py      # SQLAlchemy SessionLocal and engine setup
│   ├── utils/              # Helper utilities and background configurations
│   │   ├── celery_app.py   # Celery worker and task configurations
│   │   ├── otp.py          # OTP generation, caching, and validation
│   │   ├── redis_utils.py  # Redis client helper
│   │   └── settings.py     # Pydantic settings loading from environment variables
│   └── v1/                 # API Version 1 Namespace
│       ├── models/         # SQLAlchemy Database Models
│       │   ├── base_class.py       # Custom Declarative Base
│       │   ├── user.py             # User accounts and roles
│       │   ├── vendor.py           # Food and grocery vendor information
│       │   ├── product.py          # Vendor items (dishes, groceries)
│       │   ├── order.py            # Orders and parent-suborder relations
│       │   ├── order_item.py       # Order products and quantities
│       │   ├── scheduled_meal.py   # Pre-scheduled "111" meals (breakfast, lunch, dinner)
│       │   ├── marketplace.py      # Grocery roster subscriptions
│       │   └── analytics_summary.py # Dataclass representing operations dashboard metrics
│       ├── schema/         # Pydantic Schemas (Data validation and serialization)
│       │   ├── user.py
│       │   ├── vendor.py
│       │   ├── product.py
│       │   ├── order.py
│       │   ├── scheduled_meal.py
│       │   ├── marketplace.py
│       │   └── analytics.py
│       ├── services/       # Service Layer (Encapsulates business/database operations)
│       │   ├── user.py
│       │   ├── vendor.py
│       │   ├── product.py
│       │   ├── order.py
│       │   ├── cart.py             # Redis-backed shopping cart logic
│       │   ├── scheduled_meal.py
│       │   ├── marketplace.py
│       │   └── analytics.py        # Computes metrics and stats
│       └── routes/         # API Endpoint Routers
│           ├── user.py             # Auth, registration, OTP validation
│           ├── browse.py           # Vendor directory and product listings
│           ├── cart.py             # Add, view, and clear cart endpoints
│           ├── orders.py           # Checkout and order listings
│           └── analytics.py        # Dashboard stats and order revenue CSV export
├── scripts/                # Administrative & seeding scripts
│   └── seed_db.py          # Seeds the database with mock vendors, products, and categories
├── tests/                  # Pytest automated test suite
│   ├── conftest.py         # Test configuration and SQLite setup
│   ├── test_models.py      # Models integrity tests
│   ├── test_user_auth.py   # Registration, login, OTP workflow tests
│   ├── test_browse_commerce.py # Browse and order workflow tests
│   └── test_analytics.py   # Stats summary and CSV export tests
├── main.py                 # FastAPI Application entry point and Middleware configuration
├── requirements.txt        # Python package dependencies
├── alembic.ini             # Alembic configuration
└── .env                    # System environment variables
```

---

## 🛠️ Core Technology Stack

- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous python server framework)
- **Database Engine**: [PostgreSQL](https://www.postgresql.org/) (for relational operations, users, orders, subscriptions)
- **ORM / Query Builder**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/)
- **Cache & Message Broker**: [Redis](https://redis.io/) (used for fast cart operations and OTP cache storage)
- **Task Queue**: [Celery](https://docs.celeryq.dev/en/stable/) (handles deferred background jobs)
- **Migrations**: [Alembic](https://alembic.sqlalchemy.org/en/latest/) (for managing database schema changes)
- **Testing Suite**: [Pytest](https://docs.pytest.org/)

---

## 🚀 Getting Started

### 1. Environment Configuration
Create a `.env` file in the root directory (based on settings specified in `api/utils/settings.py`):
```env
APP_NAME="FUDS Backend"
DATABASE_URL="postgresql://user:password@localhost/fuds_db"
REDIS_URL="redis://localhost:6379/0"
```

### 2. Database Migrations
Apply database schema modifications to your active PostgreSQL instance using Alembic:
```bash
alembic upgrade head
```

### 3. Seed Database
Load sample Lagos vendors, restaurant menus, and supermarkets into your database:
```bash
python scripts/seed_db.py
```

### 4. Running the API Server
Start the development server with Hot-Reload enabled:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🧪 Testing

Run the test suite using `pytest`:
```bash
pytest
```
*Note: The test suite uses an in-memory SQLite configuration to avoid side-effects in your active database.*
