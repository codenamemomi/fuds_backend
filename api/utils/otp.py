import json
import random
import string
from datetime import datetime, timedelta
from typing import Any

from api.utils.redis_utils import redis_client


class OTPService:
    def __init__(self, length: int = 6, ttl_seconds: int = 300):
        self.length = length
        self.ttl_seconds = ttl_seconds

    def _build_key(self, purpose: str, identifier: str) -> str:
        return f"otp:{purpose}:{identifier}"

    def create_payload(self, purpose: str = "auth", identifier: str = "default") -> dict[str, Any]:
        code = "".join(random.choices(string.digits, k=self.length))
        expires_at = (datetime.utcnow() + timedelta(seconds=self.ttl_seconds)).isoformat()
        payload = {"code": code, "expires_at": expires_at, "used": False, "blacklisted": False}
        key = self._build_key(purpose, identifier)
        redis_client.setex(key, self.ttl_seconds, json.dumps(payload))
        return payload

    def is_valid(self, code: str, purpose: str = "auth", identifier: str = "default") -> bool:
        key = self._build_key(purpose, identifier)
        raw = redis_client.get(key)
        if not raw:
            return False

        payload = json.loads(raw)
        if payload.get("blacklisted") or payload.get("used"):
            return False

        if str(payload.get("code", "")) != str(code):
            return False

        expires_at = payload.get("expires_at")
        if not expires_at:
            return False

        return datetime.utcnow() <= datetime.fromisoformat(expires_at)

    def consume(self, code: str, purpose: str = "auth", identifier: str = "default") -> bool:
        key = self._build_key(purpose, identifier)
        raw = redis_client.get(key)
        if not raw:
            return False

        payload = json.loads(raw)
        if payload.get("blacklisted") or payload.get("used"):
            return False

        if not self.is_valid(code, purpose, identifier):
            return False

        payload["used"] = True
        redis_client.setex(key, 60, json.dumps(payload))
        return True

    def blacklist(self, purpose: str = "auth", identifier: str = "default") -> None:
        key = self._build_key(purpose, identifier)
        raw = redis_client.get(key)
        if not raw:
            return

        payload = json.loads(raw)
        payload["blacklisted"] = True
        redis_client.setex(key, 60, json.dumps(payload))

    def delete(self, purpose: str = "auth", identifier: str = "default") -> None:
        redis_client.delete(self._build_key(purpose, identifier))
