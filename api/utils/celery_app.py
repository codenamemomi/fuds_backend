from celery import Celery

from api.utils.settings import settings

celery_app = Celery(
    "fuds_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "api.tasks.email_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Worker reliability under load
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    # Optional: eager mode for unit tests via env CELERY_TASK_ALWAYS_EAGER=true
    task_always_eager=False,
    task_store_eager_result=True,
)


@celery_app.task
def sample_task(value: int) -> int:
    return value * 2
