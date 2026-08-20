import redis
from fastapi import HTTPException

from app.config import settings

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def enforce_rate_limit(scope: str, subject: str, limit: int, window_seconds: int) -> None:
    if limit <= 0:
        return
    key = f"rl:{scope}:{subject}"
    r = _redis()
    count = r.incr(key)
    if count == 1:
        r.expire(key, window_seconds)
    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def ping_redis() -> bool:
    try:
        return bool(_redis().ping())
    except redis.RedisError:
        return False
