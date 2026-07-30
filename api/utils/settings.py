from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "FUDS Backend"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    BACKEND_CORS_ORIGINS: list[str] = ["*"]
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    DATABASE_URL: str
    SECRET_KEY: str = "SECRET_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # ── Paystack ──────────────────────────────────────────────────────────────
    # Get keys from https://dashboard.paystack.com/#/settings/developer
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""
    PAYSTACK_BASE_URL: str = "https://api.paystack.co"
    # Default browser redirect after hosted checkout (mobile deep link or web URL)
    PAYSTACK_CALLBACK_URL: str = "https://fuds.app/payment/callback"
    # Currency ISO code; Paystack Nigeria uses NGN (amount sent in kobo)
    PAYSTACK_CURRENCY: str = "NGN"
    # Deprecated: was for Titan Dedicated NUBAN. Bank transfer now uses
    # Initialize Transaction with channels=["bank_transfer"] only.
    PAYSTACK_TRANSFER_BANK: str = "titan-paystack"

    # ── Email (registration OTP & transactional) ──────────────────────────────
    # provider: console | brevo | smtp
    #   console — log only (local / CI tests; no network)
    #   brevo   — Brevo transactional API (https://app.brevo.com)
    #   smtp    — generic SMTP (Gmail, SES, Mailgun, etc.)
    EMAIL_PROVIDER: str = "console"
    EMAIL_FROM: str = "FUDS <noreply@example.com>"
    EMAIL_REPLY_TO: str = ""
    # When True, enqueue Celery task (scales out with workers). Falls back to
    # inline send if the broker is unreachable so register never 500s on email.
    EMAIL_ASYNC: bool = True
    # Brevo (Sendinblue) — API key from https://app.brevo.com/settings/keys/api
    BREVO_API_KEY: str = ""
    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    # OTP delivery
    OTP_TTL_SECONDS: int = 300
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    APP_PUBLIC_NAME: str = "FUDS"


settings = Settings()
