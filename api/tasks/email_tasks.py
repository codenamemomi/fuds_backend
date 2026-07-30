"""
Async email tasks.

Run a worker:
  celery -A api.utils.celery_app.celery_app worker -l info

Scale horizontally by adding more workers sharing the same Redis broker.
"""

from __future__ import annotations

import logging

from api.utils.celery_app import celery_app
from api.utils.email_service import EmailError, EmailService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="fuds.send_registration_otp_email",
    bind=True,
    max_retries=5,
    default_retry_delay=15,
    acks_late=True,
    # Don't flood the provider on poison messages forever
    autoretry_for=(EmailError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def send_registration_otp_email(
    self,
    to: str,
    code: str,
    fullname: str = "",
) -> dict:
    """
    Deliver registration OTP via configured provider.

    Retries with exponential backoff so transient SMTP/API failures don't
    drop codes under load.
    """
    try:
        EmailService().send_registration_otp(
            to=to,
            code=code,
            fullname=fullname or None,
        )
        return {"status": "sent", "to": to}
    except EmailError as exc:
        logger.warning("OTP email attempt failed for %s: %s", to, exc)
        raise
