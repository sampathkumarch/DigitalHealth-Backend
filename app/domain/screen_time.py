from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.errors import DomainError

PARTIAL = "partial"
FINAL = "final"
HOUR_MS = 60 * 60 * 1000
MAX_SCREEN_ON_MS = 25 * HOUR_MS
MAX_APP_MS = 24 * HOUR_MS
MAX_APPS = 50
MAX_DAYS = 14
CAPTURE_SKEW = timedelta(minutes=5)
PACKAGE_MAX = 200
LABEL_MAX = 120
TIMEZONE_MAX = 64


@dataclass(frozen=True)
class ScreenTimeApp:
    package_name: str
    label: str
    visible_ms: int
    launch_count: int


@dataclass(frozen=True)
class ScreenTimeAppDraft:
    package_name: str
    label: str
    visible_ms: int
    launch_count: int


@dataclass(frozen=True)
class ScreenTimeDraft:
    device_id: UUID
    local_date: date
    timezone: str
    status: str
    screen_on_ms: int
    hours: tuple[int, ...]
    captured_at: datetime
    apps: tuple[ScreenTimeAppDraft, ...]


@dataclass(frozen=True)
class ScreenTimeDay:
    user_id: UUID
    device_id: UUID
    local_date: date
    timezone: str
    status: str
    screen_on_ms: int
    hours: tuple[int, ...]
    captured_at: datetime
    apps: tuple[ScreenTimeApp, ...]


def clean_days(drafts: list[ScreenTimeDraft], now: datetime) -> list[ScreenTimeDay]:
    if not drafts:
        raise DomainError("Choose at least one day.", {"days": "Choose at least one day."})
    if len(drafts) > MAX_DAYS:
        raise DomainError(
            "Send at most 14 days at a time.",
            {"days": "Send at most 14 days at a time."},
        )
    dates = [item.local_date for item in drafts]
    if len(set(dates)) != len(dates):
        raise DomainError("Each day can only be sent once.", {"local_date": "Each day can only be sent once."})
    cleaned = [clean_day(item, now) for item in drafts]
    return cleaned


def clean_day(draft: ScreenTimeDraft, now: datetime) -> ScreenTimeDay:
    zone = _zone(draft.timezone)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.astimezone(zone).date()
    if draft.local_date > today:
        raise DomainError(
            "That day is still in the future.",
            {"local_date": "That day is still in the future."},
        )
    if draft.status not in (PARTIAL, FINAL):
        raise DomainError("Choose a valid day status.", {"status": "Choose a valid day status."})
    captured = _captured_at(draft.captured_at, now)
    hours = _hours(draft.hours)
    screen_on = _clamp(draft.screen_on_ms, MAX_SCREEN_ON_MS)
    if screen_on == 0:
        screen_on = min(sum(hours), MAX_SCREEN_ON_MS)
    apps = _apps(draft.apps)
    return ScreenTimeDay(
        user_id=UUID(int=0),
        device_id=draft.device_id,
        local_date=draft.local_date,
        timezone=str(zone),
        status=draft.status,
        screen_on_ms=screen_on,
        hours=hours,
        captured_at=captured,
        apps=apps,
    )


def should_keep_existing(existing: ScreenTimeDay, incoming: ScreenTimeDay) -> bool:
    if existing.captured_at >= incoming.captured_at:
        return True
    return existing.status == FINAL and incoming.status == PARTIAL


def _zone(name: str) -> ZoneInfo:
    text = name.strip()
    if not text or len(text) > TIMEZONE_MAX:
        raise DomainError("Choose a valid timezone.", {"timezone": "Choose a valid timezone."})
    try:
        return ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise DomainError("Choose a valid timezone.", {"timezone": "Choose a valid timezone."}) from exc


def _captured_at(value: datetime, now: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    captured = value.astimezone(timezone.utc)
    latest = now.astimezone(timezone.utc) + CAPTURE_SKEW
    if captured > latest:
        return latest
    return captured


def _hours(values: tuple[int, ...]) -> tuple[int, ...]:
    cleaned: list[int] = []
    for index in range(24):
        value = values[index] if index < len(values) else 0
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            cleaned.append(0)
            continue
        cleaned.append(min(value, HOUR_MS))
    return tuple(cleaned)


def _apps(apps: tuple[ScreenTimeAppDraft, ...]) -> tuple[ScreenTimeApp, ...]:
    merged: dict[str, ScreenTimeApp] = {}
    for app in apps:
        package = app.package_name.strip()
        if not package or len(package) > PACKAGE_MAX or any(char.isspace() for char in package):
            continue
        label = app.label.strip()[:LABEL_MAX]
        visible = _clamp(app.visible_ms, MAX_APP_MS)
        if visible <= 0:
            continue
        launches = _clamp(app.launch_count, 10_000)
        current = merged.get(package)
        if current is None:
            merged[package] = ScreenTimeApp(package, label or package, visible, launches)
            continue
        merged[package] = ScreenTimeApp(
            package,
            label or current.label,
            min(MAX_APP_MS, current.visible_ms + visible),
            min(10_000, current.launch_count + launches),
        )
    ordered = tuple(sorted(merged.values(), key=lambda item: (-item.visible_ms, item.label.casefold())))
    return ordered[:MAX_APPS]


def _clamp(value: int, limit: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return 0
    return min(value, limit)
