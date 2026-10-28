from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.screen_time import ScreenTimeAppDraft, ScreenTimeDay, ScreenTimeDraft


class ScreenTimeAppIn(BaseModel):
    package_name: str
    label: str = ""
    visible_ms: int
    launch_count: int = 0


class ScreenTimeDayIn(BaseModel):
    local_date: date
    timezone: str
    status: str
    screen_on_ms: int
    hours: list[int] = Field(min_length=24, max_length=24)
    captured_at: datetime
    apps: list[ScreenTimeAppIn] = Field(default_factory=list, max_length=50)


class ReplaceScreenTimeRequest(BaseModel):
    device_id: UUID
    days: list[ScreenTimeDayIn] = Field(min_length=1, max_length=14)


class ScreenTimeAppResponse(BaseModel):
    package_name: str
    label: str
    visible_ms: int
    launch_count: int


class ScreenTimeDayResponse(BaseModel):
    device_id: UUID
    local_date: date
    timezone: str
    status: str
    screen_on_ms: int
    hours: list[int]
    captured_at: datetime
    apps: list[ScreenTimeAppResponse]


class ScreenTimeDaysResponse(BaseModel):
    days: list[ScreenTimeDayResponse]


def drafts_from_request(body: ReplaceScreenTimeRequest) -> list[ScreenTimeDraft]:
    return [
        ScreenTimeDraft(
            device_id=body.device_id,
            local_date=day.local_date,
            timezone=day.timezone,
            status=day.status,
            screen_on_ms=day.screen_on_ms,
            hours=tuple(day.hours),
            captured_at=day.captured_at,
            apps=tuple(
                ScreenTimeAppDraft(
                    package_name=app.package_name,
                    label=app.label,
                    visible_ms=app.visible_ms,
                    launch_count=app.launch_count,
                )
                for app in day.apps
            ),
        )
        for day in body.days
    ]


def days_response(days: list[ScreenTimeDay]) -> ScreenTimeDaysResponse:
    return ScreenTimeDaysResponse(
        days=[
            ScreenTimeDayResponse(
                device_id=day.device_id,
                local_date=day.local_date,
                timezone=day.timezone,
                status=day.status,
                screen_on_ms=day.screen_on_ms,
                hours=list(day.hours),
                captured_at=day.captured_at,
                apps=[
                    ScreenTimeAppResponse(
                        package_name=app.package_name,
                        label=app.label,
                        visible_ms=app.visible_ms,
                        launch_count=app.launch_count,
                    )
                    for app in day.apps
                ],
            )
            for day in days
        ]
    )
