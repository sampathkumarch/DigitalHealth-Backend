import time
from collections import defaultdict

from app.core.exceptions import RateLimitError


class MemoryRateLimiter:
    """In-process limiter for tests. Production uses Redis."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    def hit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        message: str,
    ) -> None:
        now = time.monotonic()
        window_start = now - window_seconds
        hits = [stamp for stamp in self._hits[key] if stamp > window_start]
        if len(hits) >= limit:
            self._hits[key] = hits
            raise RateLimitError(message, retry_after=window_seconds)
        hits.append(now)
        self._hits[key] = hits

    def travel(self, seconds: float) -> None:
        """Move recorded hits backward so tests can pass a cooldown window."""
        for key, hits in self._hits.items():
            self._hits[key] = [stamp - seconds for stamp in hits]


class MemoryTokenDenylist:
    def __init__(self) -> None:
        self._until: dict[str, float] = {}

    def deny(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        self._until[jti] = time.monotonic() + ttl_seconds

    def denied(self, jti: str) -> bool:
        expiry = self._until.get(jti)
        return expiry is not None and expiry > time.monotonic()
