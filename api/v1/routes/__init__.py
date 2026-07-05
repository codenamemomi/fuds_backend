from fastapi import APIRouter

from api.utils.celery_app import sample_task

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/health")
def healthcheck():
    return {"status": "ok"}


@router.post("/tasks/sample")
def trigger_sample_task(value: int = 1):
    task = sample_task.delay(value)
    return {"task_id": task.id, "status": "accepted"}


api_version_one = router
