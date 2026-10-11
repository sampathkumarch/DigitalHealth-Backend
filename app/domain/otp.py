from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


WHATSAPP = "whatsapp"
EMAIL = "email"
LOGIN = "login"
EMAIL_VERIFICATION = "email_verification"


@dataclass
class OtpChallenge:
    id: UUID
    user_id: UUID | None
    channel: str
    destination: str
    purpose: str
    code_hash: str
    code_plaintext: str | None
    expires_at: datetime
    attempt_count: int
    max_attempts: int
    consumed_at: datetime | None
    created_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def is_locked(self) -> bool:
        return self.attempt_count >= self.max_attempts
