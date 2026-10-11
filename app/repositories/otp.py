from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.otp import OtpChallenge


class OtpRepository(Protocol):
    def add(self, challenge: OtpChallenge) -> None: ...

    def save(self, challenge: OtpChallenge) -> None: ...

    def get_latest(
        self,
        *,
        channel: str,
        destination: str,
        purpose: str,
    ) -> OtpChallenge | None: ...

    def invalidate_active(
        self,
        *,
        channel: str,
        destination: str,
        purpose: str,
        now: datetime,
    ) -> None: ...

    def consume(self, challenge_id: UUID, now: datetime) -> bool: ...
