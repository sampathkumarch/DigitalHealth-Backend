from datetime import date
from typing import Protocol
from uuid import UUID

from app.domain.screen_time import ScreenTimeDay


class ScreenTimeRepository(Protocol):
    def get_day(self, user_id: UUID, device_id: UUID, local_date: date) -> ScreenTimeDay | None: ...

    def list_days(
        self,
        user_id: UUID,
        device_id: UUID,
        start: date,
        end: date,
    ) -> list[ScreenTimeDay]: ...

    def save_day(self, day: ScreenTimeDay) -> None: ...
