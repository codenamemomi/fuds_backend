from fastapi import APIRouter

from api.utils.celery_app import sample_task
from api.v1.routes.analytics import router as analytics_router
from api.v1.routes.browse import router as browse_router
from api.v1.routes.cart import router as cart_router
from api.v1.routes.orders import router as orders_router
from api.v1.routes.payments import router as payments_router
from api.v1.routes.user import router as user_router

router = APIRouter(prefix="/api/v1", tags=["v1"])
router.include_router(user_router)
router.include_router(browse_router)
router.include_router(cart_router)
router.include_router(orders_router)
router.include_router(payments_router)
router.include_router(analytics_router)



@router.get("/health")
def healthcheck():
    return {"status": "ok"}


@router.post("/tasks/sample")
def trigger_sample_task(value: int = 1):
    task = sample_task.delay(value)
    return {"task_id": task.id, "status": "accepted"}


api_version_one = router

