import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.utils.settings import settings
from api.v1.routes import api_version_one

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s — %(message)s",
)
log = logging.getLogger("startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: mounts and verifies all services before serving traffic.
      1. PostgreSQL DB  — test connection via engine ping
      2. Redis          — PING command
      3. Celery broker  — connection reachability check
      4. Cache warm     — pre-populate browse data into Redis
    """

    # ── 1. PostgreSQL ──────────────────────────────────────────────────────────
    from api.db.session import SessionLocal, engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("✅ [startup] PostgreSQL — connected")
    except Exception as e:
        log.error(f"❌ [startup] PostgreSQL — FAILED: {e}")

    # ── 2. Redis ───────────────────────────────────────────────────────────────
    from api.utils.redis_utils import ping_redis
    try:
        if ping_redis():
            log.info("✅ [startup] Redis      — connected")
        else:
            log.error("❌ [startup] Redis      — PING returned False")
    except Exception as e:
        log.error(f"❌ [startup] Redis      — FAILED: {e}")

    # ── 3. Celery broker ───────────────────────────────────────────────────────
    from api.utils.settings import settings
    try:
        import redis as _redis
        broker = _redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)
        broker.ping()
        log.info("✅ [startup] Celery broker — connected")
        broker.close()
    except Exception as e:
        log.warning(f"⚠️  [startup] Celery broker — unreachable (workers may be offline): {e}")

    # ── 4. Pre-warm cache ─────────────────────────────────────────────────────
    from api.v1.services.browse import BrowseService
    db = SessionLocal()
    try:
        log.info("⏳ [startup] Warming Redis browse cache...")
        BrowseService(db).warm_cache()
        log.info("✅ [startup] Cache warm   — complete")
    except Exception as e:
        log.error(f"❌ [startup] Cache warm   — FAILED: {e}")
    finally:
        db.close()

    yield
    log.info("🛑 [shutdown] Application shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(api_version_one)


@app.get("/")
def healthcheck():
    return {"status": "ok"}
