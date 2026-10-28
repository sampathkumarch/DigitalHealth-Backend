"""Keep each day's apps in screen_time_apps.

The apps for one day are one JSONB list. Databases that stored that list on
screen_time_days, or as one row per app, are copied into this table.
"""

from collections.abc import Sequence

from alembic import op

from app.infrastructure.db.schema import separate_screen_time_apps

revision: str = "20261027_0004"
down_revision: str | None = "20261027_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    separate_screen_time_apps(op.get_bind())


def downgrade() -> None:
    op.execute("ALTER TABLE screen_time_days ADD COLUMN IF NOT EXISTS apps JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute(
        """
        UPDATE screen_time_days AS day
        SET apps = app_row.apps
        FROM screen_time_apps AS app_row
        WHERE app_row.day_id = day.id
        """
    )
    op.execute("DROP TABLE IF EXISTS screen_time_apps")
