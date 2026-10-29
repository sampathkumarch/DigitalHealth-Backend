from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.screen_time import ScreenTimeApp, ScreenTimeDay
from app.infrastructure.db.models import ScreenTimeAppsModel, ScreenTimeDayModel
from app.infrastructure.db.schema import ensure_screen_time_tables


class SqlScreenTimeRepository:
    def __init__(self, session: Session) -> None:
        ensure_screen_time_tables()
        self._session = session

    def get_day(self, user_id: UUID, device_id: UUID, local_date: date) -> ScreenTimeDay | None:
        row = self._session.scalar(
            select(ScreenTimeDayModel).where(
                ScreenTimeDayModel.user_id == user_id,
                ScreenTimeDayModel.device_id == device_id,
                ScreenTimeDayModel.local_date == local_date,
            )
        )
        if row is None:
            return None
        return _to_day(row, self._apps_by_day([row.id]).get(row.id))

    def list_days(self, user_id: UUID, device_id: UUID, start: date, end: date) -> list[ScreenTimeDay]:
        rows = self._session.scalars(
            select(ScreenTimeDayModel)
            .where(
                ScreenTimeDayModel.user_id == user_id,
                ScreenTimeDayModel.device_id == device_id,
                ScreenTimeDayModel.local_date >= start,
                ScreenTimeDayModel.local_date <= end,
            )
            .order_by(ScreenTimeDayModel.local_date)
        ).all()
        apps = self._apps_by_day([row.id for row in rows])
        return [_to_day(row, apps.get(row.id)) for row in rows]

    def day_span(self, user_id: UUID, device_id: UUID) -> tuple[date | None, date | None, UUID | None]:
        row = self._session.execute(
            select(
                func.min(ScreenTimeDayModel.local_date),
                func.max(ScreenTimeDayModel.local_date),
            ).where(
                ScreenTimeDayModel.user_id == user_id,
                ScreenTimeDayModel.device_id == device_id,
            )
        ).one()
        if row[0] is not None:
            return row[0], row[1], device_id
        grouped = self._session.execute(
            select(
                ScreenTimeDayModel.device_id,
                func.min(ScreenTimeDayModel.local_date),
                func.max(ScreenTimeDayModel.local_date),
            )
            .where(ScreenTimeDayModel.user_id == user_id)
            .group_by(ScreenTimeDayModel.device_id)
        ).all()
        if not grouped:
            return None, None, None
        best = min(grouped, key=lambda item: item[1])
        return best[1], best[2], best[0]

    def save_day(self, day: ScreenTimeDay) -> None:
        row = self._session.scalar(
            select(ScreenTimeDayModel).where(
                ScreenTimeDayModel.user_id == day.user_id,
                ScreenTimeDayModel.device_id == day.device_id,
                ScreenTimeDayModel.local_date == day.local_date,
            )
        )
        now = datetime.now(timezone.utc)
        if row is None:
            row = ScreenTimeDayModel(
                id=uuid4(),
                user_id=day.user_id,
                device_id=day.device_id,
                local_date=day.local_date,
                timezone=day.timezone,
                status=day.status,
                screen_on_ms=day.screen_on_ms,
                hours=list(day.hours),
                captured_at=day.captured_at,
                created_at=now,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.timezone = day.timezone
            row.status = day.status
            row.screen_on_ms = day.screen_on_ms
            row.hours = list(day.hours)
            row.captured_at = day.captured_at
            row.updated_at = now
        self._session.flush()
        self._save_apps(row.id, apps_to_json(day.apps))

    def save_days(self, days: list[ScreenTimeDay]) -> None:
        if not days:
            return
        dates = [day.local_date for day in days]
        rows = self._session.scalars(
            select(ScreenTimeDayModel).where(
                ScreenTimeDayModel.user_id == days[0].user_id,
                ScreenTimeDayModel.device_id == days[0].device_id,
                ScreenTimeDayModel.local_date.in_(dates),
            )
        ).all()
        by_date = {row.local_date: row for row in rows}
        now = datetime.now(timezone.utc)
        for day in days:
            row = by_date.get(day.local_date)
            if row is None:
                row = ScreenTimeDayModel(
                    id=uuid4(),
                    user_id=day.user_id,
                    device_id=day.device_id,
                    local_date=day.local_date,
                    timezone=day.timezone,
                    status=day.status,
                    screen_on_ms=day.screen_on_ms,
                    hours=list(day.hours),
                    captured_at=day.captured_at,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(row)
                by_date[day.local_date] = row
            else:
                row.timezone = day.timezone
                row.status = day.status
                row.screen_on_ms = day.screen_on_ms
                row.hours = list(day.hours)
                row.captured_at = day.captured_at
                row.updated_at = now
            self._session.flush()
            self._save_apps(row.id, apps_to_json(day.apps))

    def _apps_by_day(self, day_ids: list[UUID]) -> dict[UUID, object]:
        if not day_ids:
            return {}
        rows = self._session.scalars(
            select(ScreenTimeAppsModel).where(ScreenTimeAppsModel.day_id.in_(day_ids))
        ).all()
        return {row.day_id: row.apps for row in rows}

    def _save_apps(self, day_id: UUID, apps: list[dict[str, str | int]]) -> None:
        row = self._session.get(ScreenTimeAppsModel, day_id)
        if row is None:
            self._session.add(ScreenTimeAppsModel(day_id=day_id, apps=apps))
        else:
            row.apps = apps
        self._session.flush()


def apps_to_json(apps: tuple[ScreenTimeApp, ...]) -> list[dict[str, str | int]]:
    return [
        {
            "package_name": app.package_name,
            "label": app.label,
            "visible_ms": app.visible_ms,
            "launch_count": app.launch_count,
        }
        for app in apps
    ]


def apps_from_json(raw: object) -> tuple[ScreenTimeApp, ...]:
    if not isinstance(raw, list):
        return ()
    apps: list[ScreenTimeApp] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        package_name = str(item.get("package_name") or "").strip()
        if not package_name:
            continue
        try:
            visible_ms = int(item.get("visible_ms") or 0)
            launch_count = int(item.get("launch_count") or 0)
        except (TypeError, ValueError):
            continue
        if visible_ms <= 0:
            continue
        apps.append(
            ScreenTimeApp(
                package_name=package_name,
                label=str(item.get("label") or package_name),
                visible_ms=visible_ms,
                launch_count=max(0, launch_count),
            )
        )
    return tuple(sorted(apps, key=lambda app: (-app.visible_ms, app.label.casefold())))


def _to_day(row: ScreenTimeDayModel, apps: object) -> ScreenTimeDay:
    return ScreenTimeDay(
        user_id=row.user_id,
        device_id=row.device_id,
        local_date=row.local_date,
        timezone=row.timezone,
        status=row.status,
        screen_on_ms=row.screen_on_ms,
        hours=tuple(int(value) for value in row.hours),
        captured_at=row.captured_at,
        apps=apps_from_json(apps),
    )
