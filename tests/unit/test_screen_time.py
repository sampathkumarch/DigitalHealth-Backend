from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.exceptions import ValidationFailed
from app.domain.screen_time import (
    ScreenTimeApp,
    ScreenTimeAppDraft,
    ScreenTimeDay,
    ScreenTimeDraft,
    clean_days,
)
from app.infrastructure.repositories.screen_time import apps_from_json, apps_to_json
from app.domain.users import new_member
from app.services.screen_time import ScreenTimeService

NOW = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)
DEVICE = uuid4()


def _draft(**overrides) -> ScreenTimeDraft:
    values = dict(
        device_id=DEVICE,
        local_date=NOW.date(),
        timezone="Asia/Kolkata",
        status="partial",
        screen_on_ms=3_600_000,
        hours=tuple(3_600_000 if index == 10 else 0 for index in range(24)),
        captured_at=NOW,
        apps=(
            ScreenTimeAppDraft("com.whatsapp", "WhatsApp", 1_800_000, 4),
            ScreenTimeAppDraft("com.instagram.android", "Instagram", 900_000, 2),
        ),
    )
    values.update(overrides)
    return ScreenTimeDraft(**values)


class MemoryScreenTime:
    def __init__(self) -> None:
        self.days: dict[tuple, ScreenTimeDay] = {}

    def get_day(self, user_id, device_id, local_date):
        return self.days.get((user_id, device_id, local_date))

    def list_days(self, user_id, device_id, start, end):
        found = [
            day
            for (owner, device, local_date), day in self.days.items()
            if owner == user_id and device == device_id and start <= local_date <= end
        ]
        return sorted(found, key=lambda day: day.local_date)

    def save_day(self, day: ScreenTimeDay) -> None:
        self.days[(day.user_id, day.device_id, day.local_date)] = day

    def save_days(self, days: list[ScreenTimeDay]) -> None:
        for day in days:
            self.save_day(day)

    def day_span(self, user_id, device_id):
        matching = [
            (local_date, device)
            for (owner, device, local_date) in self.days
            if owner == user_id and device == device_id
        ]
        if matching:
            dates = [item[0] for item in matching]
            return min(dates), max(dates), device_id
        owned = [
            (local_date, device)
            for (owner, device, local_date) in self.days
            if owner == user_id
        ]
        if not owned:
            return None, None, None
        origin = min(item[0] for item in owned)
        device = next(item[1] for item in owned if item[0] == origin)
        last = max(item[0] for item in owned if item[1] == device)
        return origin, last, device


class Factory:
    def __init__(self, repo: MemoryScreenTime) -> None:
        self.repo = repo

    def __call__(self):
        repo = self.repo

        class Uow:
            screen_time = repo

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def commit(self):
                return None

            def rollback(self):
                return None

        return Uow()


def test_clean_day_keeps_the_chart_and_orders_apps() -> None:
    cleaned = clean_days([_draft()], NOW)[0]
    assert cleaned.screen_on_ms == 3_600_000
    assert len(cleaned.hours) == 24
    assert cleaned.hours[10] == 3_600_000
    assert [app.label for app in cleaned.apps] == ["WhatsApp", "Instagram"]


def test_a_day_from_any_past_date_can_be_stored() -> None:
    first_day = date(1990, 1, 1)
    cleaned = clean_days([_draft(local_date=first_day, status="final")], NOW)[0]
    assert cleaned.local_date == first_day
    assert cleaned.status == "final"


def test_clean_day_rejects_a_future_day_and_pads_a_short_chart() -> None:
    with pytest.raises(Exception, match="future"):
        clean_days([_draft(local_date=NOW.date() + timedelta(days=1))], NOW)
    padded = clean_days([_draft(hours=tuple([0] * 23))], NOW)[0]
    assert len(padded.hours) == 24


def test_replace_keeps_a_newer_snapshot_and_a_closed_day() -> None:
    member = new_member("+91", "9876543210", NOW)
    repo = MemoryScreenTime()
    service = ScreenTimeService(Factory(repo), clock=lambda: NOW)
    first = service.replace_days(member.id, [_draft()])
    assert first[0].apps[0].package_name == "com.whatsapp"

    older = service.replace_days(
        member.id,
        [_draft(captured_at=NOW - timedelta(minutes=5), screen_on_ms=1, hours=tuple([0] * 24))],
    )
    assert older[0].screen_on_ms == 3_600_000

    closed = _draft(status="final", captured_at=NOW + timedelta(minutes=1))
    service.replace_days(member.id, [closed])
    partial = service.replace_days(
        member.id,
        [_draft(status="partial", captured_at=NOW + timedelta(minutes=2), screen_on_ms=10)],
    )
    assert partial[0].status == "final"
    assert partial[0].screen_on_ms == 3_600_000


def test_span_returns_the_first_and_last_stored_day() -> None:
    member = new_member("+91", "9876543210", NOW)
    repo = MemoryScreenTime()
    service = ScreenTimeService(Factory(repo), clock=lambda: NOW)
    assert service.day_span(member.id, DEVICE) == (None, None, None)
    service.replace_days(
        member.id,
        [
            _draft(local_date=NOW.date() - timedelta(days=6), status="final"),
            _draft(local_date=NOW.date(), status="partial"),
        ],
    )
    assert service.day_span(member.id, DEVICE) == (NOW.date() - timedelta(days=6), NOW.date(), DEVICE)


def test_span_falls_back_to_the_users_existing_device() -> None:
    member = new_member("+91", "9876543210", NOW)
    repo = MemoryScreenTime()
    service = ScreenTimeService(Factory(repo), clock=lambda: NOW)
    service.replace_days(
        member.id,
        [_draft(local_date=NOW.date() - timedelta(days=6), status="final")],
    )
    other = uuid4()
    origin, last, stored = service.day_span(member.id, other)
    assert stored == DEVICE
    assert origin == NOW.date() - timedelta(days=6)
    assert last == NOW.date() - timedelta(days=6)


def test_list_rejects_a_long_range() -> None:
    member = new_member("+91", "9876543210", NOW)
    service = ScreenTimeService(Factory(MemoryScreenTime()), clock=lambda: NOW)
    with pytest.raises(ValidationFailed):
        service.list_days(member.id, DEVICE, NOW.date() - timedelta(days=40), NOW.date())


def test_a_bad_app_does_not_drop_the_rest_of_the_day() -> None:
    cleaned = clean_days(
        [
            _draft(
                apps=(
                    ScreenTimeAppDraft("not an app", "Broken", 60_000, 1),
                    ScreenTimeAppDraft("com.whatsapp", "W" * 150, 60_000, 1),
                )
            )
        ],
        NOW,
    )[0]
    assert len(cleaned.apps) == 1
    assert cleaned.apps[0].package_name == "com.whatsapp"
    assert len(cleaned.apps[0].label) == 120


def test_a_week_of_days_is_stored() -> None:
    member = new_member("+91", "9876543210", NOW)
    repo = MemoryScreenTime()
    service = ScreenTimeService(Factory(repo), clock=lambda: NOW)
    drafts = [
        _draft(
            local_date=NOW.date() - timedelta(days=offset),
            status="final" if offset else "partial",
        )
        for offset in range(6, -1, -1)
    ]
    stored = service.replace_days(member.id, drafts)
    assert [day.local_date.isoformat() for day in stored] == [
        "2026-10-21",
        "2026-10-22",
        "2026-10-23",
        "2026-10-24",
        "2026-10-25",
        "2026-10-26",
        "2026-10-27",
    ]


def test_one_invalid_day_does_not_drop_the_others() -> None:
    member = new_member("+91", "9876543210", NOW)
    repo = MemoryScreenTime()
    service = ScreenTimeService(Factory(repo), clock=lambda: NOW)
    stored = service.replace_days(
        member.id,
        [
            _draft(local_date=NOW.date() - timedelta(days=1), status="final"),
            _draft(local_date=NOW.date() + timedelta(days=1)),
        ],
    )
    assert [day.local_date for day in stored] == [NOW.date() - timedelta(days=1)]


def test_zero_apps_are_dropped() -> None:
    cleaned = clean_days(
        [
            _draft(
                apps=(
                    ScreenTimeAppDraft("com.android.systemui", "System UI", 0, 3),
                    ScreenTimeAppDraft("com.whatsapp", "WhatsApp", 60_000, 1),
                )
            )
        ],
        NOW,
    )[0]
    assert [app.package_name for app in cleaned.apps] == ["com.whatsapp"]
    assert isinstance(cleaned.apps[0], ScreenTimeApp)


def test_apps_round_trip_through_one_json_list() -> None:
    apps = (
        ScreenTimeApp("com.whatsapp", "WhatsApp", 60_000, 2),
        ScreenTimeApp("com.instagram.android", "Instagram", 30_000, 1),
    )
    stored = apps_to_json(apps)
    assert stored == [
        {"package_name": "com.whatsapp", "label": "WhatsApp", "visible_ms": 60_000, "launch_count": 2},
        {"package_name": "com.instagram.android", "label": "Instagram", "visible_ms": 30_000, "launch_count": 1},
    ]
    restored = apps_from_json([stored[1], {"package_name": "bad", "visible_ms": 0}, "skip", stored[0]])
    assert [app.package_name for app in restored] == ["com.whatsapp", "com.instagram.android"]
