import logging

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.exceptions import RateLimitError, ServiceUnavailable

logger = logging.getLogger(__name__)

_client: Redis | None = None

_HIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def ping_redis() -> None:
    get_redis().ping()


class RedisRateLimiter:
    def __init__(self, client: Redis) -> None:
        self._script = client.register_script(_HIT_SCRIPT)

    def hit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        message: str,
    ) -> None:
        try:
            count, ttl = self._script(keys=[f"rl:{key}"], args=[window_seconds])
        except RedisError as exc:
            logger.exception("rate limit store unavailable")
            raise ServiceUnavailable() from exc
        if int(count) > limit:
            retry_after = int(ttl) if int(ttl) > 0 else window_seconds
            raise RateLimitError(message, retry_after=retry_after)


class RedisTokenDenylist:
    def __init__(self, client: Redis) -> None:
        self._client = client

    def deny(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        try:
            self._client.setex(f"deny:{jti}", ttl_seconds, "1")
        except RedisError:
            logger.exception("token denylist write failed")

    def denied(self, jti: str) -> bool:
        try:
            return bool(self._client.exists(f"deny:{jti}"))
        except RedisError:
            logger.exception("token denylist read failed")
            return False
