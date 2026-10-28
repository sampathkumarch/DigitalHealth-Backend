"""Add daily screen time snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261027_0003"
down_revision: str | None = "20261011_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    exists = op.get_bind().execute(sa.text("SELECT to_regclass('public.screen_time_days')")).scalar()
    if exists:
        return
    op.create_table(
        "screen_time_days",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("screen_on_ms", sa.Integer(), nullable=False),
        sa.Column("hours", postgresql.JSONB(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "device_id", "local_date", name="uq_screen_time_day"),
        sa.CheckConstraint("status IN ('partial', 'final')", name="ck_screen_time_status"),
    )
    op.create_index("ix_screen_time_user_date", "screen_time_days", ["user_id", "local_date"])


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS screen_time_apps")
    op.drop_index("ix_screen_time_user_date", table_name="screen_time_days")
    op.drop_table("screen_time_days")
