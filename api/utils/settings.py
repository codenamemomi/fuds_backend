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
    # Dedicated Virtual Account provider for pay-with-transfer (Paystack Titan)
    # See: preferred_bank on POST /dedicated_account — "titan-paystack"
    PAYSTACK_TRANSFER_BANK: str = "titan-paystack"


settings = Settings()
