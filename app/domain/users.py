from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class HealthProfile:
    full_name: str = ""
    date_of_birth: date | None = None
    weight_kg: Decimal | None = None
    blood_group: str | None = None
    conditions: tuple[str, ...] = ()
    other_condition: str = ""
    photo_file_id: UUID | None = None
    profile_completed: bool = False


@dataclass
class UserAccount:
    id: UUID
    country_code: str
    phone: str
    phone_verified_at: datetime | None
    email: str | None
    email_verified_at: datetime | None
    role: str
    status: str
    profile: HealthProfile = field(default_factory=HealthProfile)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def e164(self) -> str:
        return f"{self.country_code}{self.phone}"


def new_member(country_code: str, phone: str, now: datetime) -> UserAccount:
    return UserAccount(
        id=uuid4(),
        country_code=country_code,
        phone=phone,
        phone_verified_at=now,
        email=None,
        email_verified_at=None,
        role="member",
        status="active",
        profile=HealthProfile(),
        created_at=now,
        updated_at=now,
    )
