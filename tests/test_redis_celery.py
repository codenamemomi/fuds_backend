from api.utils.celery_app import celery_app
from api.utils.settings import settings


def test_celery_app_configuration():
    assert celery_app.main == "fuds_backend"
    assert celery_app.conf["broker_url"] == settings.CELERY_BROKER_URL
    assert celery_app.conf["result_backend"] == settings.CELERY_RESULT_BACKEND
