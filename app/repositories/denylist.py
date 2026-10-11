from typing import Protocol


class TokenDenylist(Protocol):
    def deny(self, jti: str, ttl_seconds: int) -> None: ...

    def denied(self, jti: str) -> bool: ...
