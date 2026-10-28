"""Create tables the app needs when a database is behind the code."""

from sqlalchemy import text
from sqlalchemy.engine import Connection

_ready = False


def ensure_screen_time_tables() -> None:
    """Create the day table, then keep each day's apps in their own table."""
    global _ready
    if _ready:
        return
    from sqlalchemy import inspect

    from app.infrastructure.db.models import ScreenTimeDayModel
    from app.infrastructure.db.session import get_engine

    engine = get_engine()
    with engine.begin() as connection:
        existing = set(inspect(connection).get_table_names())
        if ScreenTimeDayModel.__tablename__ not in existing:
            ScreenTimeDayModel.__table__.create(bind=connection)
        separate_screen_time_apps(connection)
    _ready = True


def separate_screen_time_apps(connection: Connection) -> None:
    """Store the apps JSON on screen_time_apps, one row for each day.

    Older databases may still have one row per app, or the JSON list on
    screen_time_days. Both are copied forward and then removed.
    """
    if not _exists(connection, "screen_time_days"):
        return
    if _column(connection, "screen_time_apps", "package_name"):
        _fold_legacy_app_rows(connection)
    if not _column(connection, "screen_time_apps", "apps"):
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS screen_time_apps (
                    day_id UUID PRIMARY KEY REFERENCES screen_time_days(id) ON DELETE CASCADE,
                    apps JSONB NOT NULL DEFAULT '[]'::jsonb
                )
                """
            )
        )
    if _column(connection, "screen_time_days", "apps"):
        connection.execute(
            text(
                """
                INSERT INTO screen_time_apps (day_id, apps)
                SELECT id, COALESCE(apps, '[]'::jsonb)
                FROM screen_time_days
                ON CONFLICT (day_id) DO UPDATE SET apps = EXCLUDED.apps
                """
            )
        )
        connection.execute(text("ALTER TABLE screen_time_days DROP COLUMN apps"))


def _fold_legacy_app_rows(connection: Connection) -> None:
    if not _column(connection, "screen_time_days", "apps"):
        connection.execute(
            text("ALTER TABLE screen_time_days ADD COLUMN apps JSONB NOT NULL DEFAULT '[]'::jsonb")
        )
    connection.execute(
        text(
            """
            UPDATE screen_time_days AS day
            SET apps = COALESCE((
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'package_name', app.package_name,
                        'label', app.label,
                        'visible_ms', app.visible_ms,
                        'launch_count', app.launch_count
                    )
                    ORDER BY app.visible_ms DESC, lower(app.label)
                )
                FROM screen_time_apps AS app
                WHERE app.day_id = day.id
            ), '[]'::jsonb)
            WHERE EXISTS (
                SELECT 1 FROM screen_time_apps AS app WHERE app.day_id = day.id
            )
            """
        )
    )
    connection.execute(text("DROP TABLE screen_time_apps"))


def _exists(connection: Connection, table_name: str) -> bool:
    return bool(connection.execute(text("SELECT to_regclass(:name)"), {"name": f"public.{table_name}"}).scalar())


def _column(connection: Connection, table_name: str, column_name: str) -> bool:
    found = connection.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).first()
    return found is not None
