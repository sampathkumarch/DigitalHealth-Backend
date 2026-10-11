from typing import Protocol


class RateLimiter(Protocol):
    def hit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
        message: str,
    ) -> None: ...
