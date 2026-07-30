"""Unit tests for registration OTP email dispatch."""

from unittest.mock import MagicMock, patch

from api.utils.email_service import EmailService, dispatch_registration_otp
from api.utils import settings as settings_module


def test_console_provider_sends_without_network():
    with patch.object(settings_module.settings, "EMAIL_PROVIDER", "console"):
        EmailService().send_registration_otp(
            to="user@example.com",
            code="123456",
            fullname="Ada Lovelace",
        )


def test_dispatch_async_enqueues_celery_task():
    with patch.object(settings_module.settings, "EMAIL_ASYNC", True):
        with patch("api.tasks.email_tasks.send_registration_otp_email") as task:
            task.delay = MagicMock()
            dispatch_registration_otp(to="a@b.com", code="999111", fullname="Test")
            task.delay.assert_called_once_with("a@b.com", "999111", "Test")


def test_dispatch_sync_when_async_disabled():
    with patch.object(settings_module.settings, "EMAIL_ASYNC", False):
        with patch.object(EmailService, "send_registration_otp") as send:
            dispatch_registration_otp(to="a@b.com", code="111222", fullname="X")
            send.assert_called_once()
