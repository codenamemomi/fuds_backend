"""
Transactional email delivery for FUDS.

Providers (settings.EMAIL_PROVIDER):
  - console — log body (dev / CI; no external calls)
  - brevo   — Brevo (Sendinblue) transactional HTTP API
  - smtp    — classic SMTP via smtplib

Call sites should prefer `dispatch_registration_otp()` which enqueues a Celery
task when EMAIL_ASYNC is on, so HTTP workers stay free under load.
"""

from __future__ import annotations

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from api.utils.settings import settings

logger = logging.getLogger(__name__)

# "Name <email@x.com>" or bare "email@x.com"
_FROM_RE = re.compile(r"^\s*(?:(?P<name>.+?)\s*)?<(?P<email>[^>]+)>\s*$")


class EmailError(Exception):
    """Raised when a provider fails to accept a message."""


def parse_from_address(value: str) -> tuple[str, str]:
    """Return (display_name, email) from EMAIL_FROM."""
    raw = (value or "").strip()
    m = _FROM_RE.match(raw)
    if m:
        name = (m.group("name") or "").strip().strip('"') or settings.APP_PUBLIC_NAME
        return name, m.group("email").strip()
    if "@" in raw:
        return settings.APP_PUBLIC_NAME, raw
    return settings.APP_PUBLIC_NAME, raw


def _registration_otp_html(
    *,
    code: str,
    fullname: str | None,
    ttl_minutes: int,
    app_name: str,
) -> str:
    greeting = f"Hi {fullname.split()[0]}," if fullname and fullname.strip() else "Hi there,"
    return f"""\
<!DOCTYPE html>
<html>
<body style="font-family: Inter, system-ui, sans-serif; background:#F1EFE8; padding:32px;">
  <div style="max-width:480px;margin:0 auto;background:#fff;border-radius:16px;
              padding:32px;border:1px solid #D8D4C8;">
    <div style="font-size:22px;font-weight:900;color:#085041;letter-spacing:3px;">
      {app_name}
    </div>
    <p style="color:#0F172A;font-size:16px;margin-top:24px;">{greeting}</p>
    <p style="color:#64748b;font-size:14px;line-height:1.5;">
      Use this code to verify your email and activate your account.
      It expires in <strong>{ttl_minutes} minutes</strong>.
    </p>
    <div style="margin:28px 0;text-align:center;">
      <span style="display:inline-block;letter-spacing:10px;font-size:32px;
                   font-weight:800;color:#1D9E75;background:#ECFDF5;
                   padding:16px 24px;border-radius:12px;">{code}</span>
    </div>
    <p style="color:#94a3b8;font-size:12px;line-height:1.5;">
      If you didn&apos;t create a {app_name} account, you can ignore this email.
    </p>
  </div>
</body>
</html>
"""


def _registration_otp_text(
    *,
    code: str,
    fullname: str | None,
    ttl_minutes: int,
    app_name: str,
) -> str:
    greeting = f"Hi {fullname.split()[0]}," if fullname and fullname.strip() else "Hi there,"
    return (
        f"{greeting}\n\n"
        f"Your {app_name} verification code is: {code}\n\n"
        f"It expires in {ttl_minutes} minutes.\n"
        f"If you didn't request this, ignore this email.\n"
    )


class EmailService:
    """Synchronous send — safe to call from a Celery worker or inline fallback."""

    def send(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        html: Optional[str] = None,
    ) -> None:
        provider = (settings.EMAIL_PROVIDER or "console").strip().lower()
        if provider in ("brevo", "sendinblue"):
            self._send_brevo(to=to, subject=subject, text=text, html=html)
        elif provider == "smtp":
            self._send_smtp(to=to, subject=subject, text=text, html=html)
        elif provider == "resend":
            # Soft redirect: Resend was removed — tell ops to switch config
            raise EmailError(
                "EMAIL_PROVIDER=resend is no longer supported. "
                "Set EMAIL_PROVIDER=brevo and BREVO_API_KEY."
            )
        else:
            self._send_console(to=to, subject=subject, text=text, html=html)

    def send_registration_otp(
        self,
        *,
        to: str,
        code: str,
        fullname: Optional[str] = None,
    ) -> None:
        app = settings.APP_PUBLIC_NAME
        ttl_min = max(1, int(settings.OTP_TTL_SECONDS) // 60)
        subject = f"{app} verification code: {code}"
        text = _registration_otp_text(
            code=code, fullname=fullname, ttl_minutes=ttl_min, app_name=app
        )
        html = _registration_otp_html(
            code=code, fullname=fullname, ttl_minutes=ttl_min, app_name=app
        )
        self.send(to=to, subject=subject, text=text, html=html)
        logger.info(
            "Registration OTP email accepted for %s via %s",
            to,
            settings.EMAIL_PROVIDER,
        )

    def _send_console(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        html: Optional[str] = None,
    ) -> None:
        logger.info(
            "[email:console] to=%s subject=%s\n%s",
            to,
            subject,
            text,
        )
        if settings.DEBUG:
            print(
                f"\n===== EMAIL (console) → {to} =====\n{subject}\n\n{text}\n"
                f"===============================\n"
            )

    def _send_brevo(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        html: Optional[str] = None,
    ) -> None:
        if not settings.BREVO_API_KEY:
            raise EmailError("BREVO_API_KEY is not configured")

        try:
            import sib_api_v3_sdk
            from sib_api_v3_sdk.rest import ApiException
        except ImportError as exc:
            raise EmailError(
                "sib-api-v3-sdk is not installed (pip install sib-api-v3-sdk)"
            ) from exc

        sender_name, sender_email = parse_from_address(settings.EMAIL_FROM)
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = settings.BREVO_API_KEY

        api = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to}],
            sender={"name": sender_name, "email": sender_email},
            subject=subject,
            html_content=html or text.replace("\n", "<br/>"),
            text_content=text,
        )
        if settings.EMAIL_REPLY_TO:
            _, reply_email = parse_from_address(settings.EMAIL_REPLY_TO)
            if "@" in reply_email:
                send_smtp_email.reply_to = {"email": reply_email}

        try:
            result = api.send_transac_email(send_smtp_email)
            msg_id = getattr(result, "message_id", None) or getattr(result, "messageId", None)
            logger.info("Brevo accepted email to %s message_id=%s", to, msg_id)
        except ApiException as exc:
            body = getattr(exc, "body", None) or str(exc)
            logger.exception("Brevo send failed for %s: %s", to, body)
            raise EmailError(f"Brevo API error: {body}") from exc
        except Exception as exc:
            logger.exception("Brevo send failed for %s", to)
            raise EmailError(str(exc)) from exc

    def _send_smtp(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        html: Optional[str] = None,
    ) -> None:
        if not settings.SMTP_HOST:
            raise EmailError("SMTP_HOST is not configured")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to
        if settings.EMAIL_REPLY_TO:
            msg["Reply-To"] = settings.EMAIL_REPLY_TO
        msg.attach(MIMEText(text, "plain", "utf-8"))
        if html:
            msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            if settings.SMTP_USE_TLS:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                    server.ehlo()
                    server.starttls()
                    if settings.SMTP_USER:
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.EMAIL_FROM, [to], msg.as_string())
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                    if settings.SMTP_USER:
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.EMAIL_FROM, [to], msg.as_string())
        except Exception as exc:
            logger.exception("SMTP send failed for %s", to)
            raise EmailError(str(exc)) from exc


def dispatch_registration_otp(
    *,
    to: str,
    code: str,
    fullname: Optional[str] = None,
) -> None:
    """
    Enqueue OTP email (async) or send inline.

    Designed so registration HTTP handlers stay fast under traffic:
    workers scale horizontally via Celery; broker outage falls back to sync.
    """
    if not to:
        logger.warning("dispatch_registration_otp called without recipient")
        return

    if settings.EMAIL_ASYNC:
        try:
            from api.tasks.email_tasks import send_registration_otp_email

            async_result = send_registration_otp_email.delay(to, code, fullname or "")
            logger.info(
                "Queued registration OTP email for %s (task_id=%s). "
                "A Celery worker must be running or the email will never send: "
                "celery -A api.utils.celery_app.celery_app worker -l info",
                to,
                getattr(async_result, "id", None),
            )
            return
        except Exception as exc:
            logger.warning(
                "Failed to enqueue OTP email for %s (%s); sending inline",
                to,
                exc,
            )

    EmailService().send_registration_otp(to=to, code=code, fullname=fullname or None)
