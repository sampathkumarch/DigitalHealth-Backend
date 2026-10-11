from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.tokens import RefreshToken


@dataclass(frozen=True)
class AccessPrincipal:
    user_id: UUID
    jti: str
    expires_at: datetime


@dataclass(frozen=True)
class IssuedAccess:
    value: str
    jti: str
    expires_in: int
    expires_at: datetime


class AccessTokens(Protocol):
    def issue_access(self, user_id: UUID) -> IssuedAccess: ...

    def decode_access(self, token: str) -> AccessPrincipal: ...

    def issue_file_access(self, file_id: UUID) -> str: ...

    def decode_file_access(self, token: str) -> UUID: ...


class RefreshTokenRepository(Protocol):
    def add(self, token: RefreshToken) -> None: ...

    def save(self, token: RefreshToken) -> None: ...

    def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    def revoke_all(self, user_id: UUID, now: datetime) -> None: ...
