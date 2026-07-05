import redis

from api.utils.settings import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
)


def ping_redis() -> bool:
    return bool(redis_client.ping())
