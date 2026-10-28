from datetime import date, datetime, timezone
from uuid import UUID

from app.core.exceptions import ValidationFailed
from app.domain.errors import DomainError
from app.domain.screen_time import (
    MAX_DAYS,
    ScreenTimeDay,
    ScreenTimeDraft,
    clean_day,
    should_keep_existing,
)
from app.repositories.unit_of_work import UnitOfWorkFactory


class ScreenTimeService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock=None) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def replace_days(self, user_id: UUID, drafts: list[ScreenTimeDraft]) -> list[ScreenTimeDay]:
        if not drafts:
            raise ValidationFailed("Choose at least one day.", {"days": "Choose at least one day."})
        now = self._clock()
        with self._uow_factory() as uow:
            stored: list[ScreenTimeDay] = []
            seen: set[tuple[UUID, object]] = set()
            for draft in drafts[:MAX_DAYS]:
                try:
                    day = _owned(user_id, clean_day(draft, now))
                except DomainError:
                    continue
                key = (day.device_id, day.local_date)
                if key in seen:
                    continue
                seen.add(key)
                existing = uow.screen_time.get_day(user_id, day.device_id, day.local_date)
                if existing is not None and should_keep_existing(existing, day):
                    stored.append(existing)
                    continue
                uow.screen_time.save_day(day)
                stored.append(day)
            if not stored:
                raise ValidationFailed("Choose a valid day.", {"days": "Choose a valid day."})
            uow.commit()
            return stored

    def list_days(self, user_id: UUID, device_id: UUID, start: date, end: date) -> list[ScreenTimeDay]:
        if end < start:
            raise ValidationFailed("Choose a valid date range.", {"to": "Choose a valid date range."})
        if (end - start).days > 31:
            raise ValidationFailed("Ask for at most 31 days.", {"to": "Ask for at most 31 days."})
        with self._uow_factory() as uow:
            return uow.screen_time.list_days(user_id, device_id, start, end)


def _owned(user_id: UUID, day: ScreenTimeDay) -> ScreenTimeDay:
    return ScreenTimeDay(
        user_id=user_id,
        device_id=day.device_id,
        local_date=day.local_date,
        timezone=day.timezone,
        status=day.status,
        screen_on_ms=day.screen_on_ms,
        hours=day.hours,
        captured_at=day.captured_at,
        apps=day.apps,
    )
