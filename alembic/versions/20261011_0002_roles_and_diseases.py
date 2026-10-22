"""Add roles, disease catalog, and user diagnoses."""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.domain.roles import ADMIN_ROLE_ID, MEMBER_ROLE_ID

revision: str = "20261011_0002"
down_revision: str | None = "20261007_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("code", sa.String),
            sa.column("name", sa.String),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": MEMBER_ROLE_ID,
                "code": "member",
                "name": "Member",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": ADMIN_ROLE_ID,
                "code": "admin",
                "name": "Admin",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    op.add_column("users", sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        sa.text("UPDATE users SET role_id = CAST(:role_id AS uuid) WHERE role = 'admin'").bindparams(
            role_id=str(ADMIN_ROLE_ID)
        )
    )
    op.execute(
        sa.text("UPDATE users SET role_id = CAST(:role_id AS uuid) WHERE role_id IS NULL").bindparams(
            role_id=str(MEMBER_ROLE_ID)
        )
    )
    op.alter_column("users", "role_id", nullable=False)
    op.create_foreign_key("fk_users_role_id", "users", "roles", ["role_id"], ["id"])
    op.drop_column("users", "role")

    op.create_table(
        "disease_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_disease_categories_name"),
    )
    op.create_table(
        "diseases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(32)),
        sa.Column("code_system", sa.String(64)),
        sa.Column("category_id", postgresql.UUID(as_uuid=True)),
        sa.Column("description", sa.String(1000)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["disease_categories.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_diseases_category_id", "diseases", ["category_id"])
    op.create_index("ix_diseases_name", "diseases", ["name"])
    op.create_index(
        "uq_diseases_code",
        "diseases",
        ["code_system", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )
    op.create_table(
        "user_diagnoses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("disease_id", postgresql.UUID(as_uuid=True)),
        sa.Column("custom_disease_name", sa.String(200)),
        sa.Column("diagnosis_status", sa.String(32), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False),
        sa.Column("diagnosed_at", sa.Date()),
        sa.Column("notes", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "disease_id IS NOT NULL OR custom_disease_name IS NOT NULL",
            name="ck_user_diagnoses_target",
        ),
        sa.CheckConstraint(
            "diagnosis_status IN ('active', 'resolved', 'entered-in-error')",
            name="ck_user_diagnoses_status",
        ),
        sa.CheckConstraint(
            "review_status IN ('confirmed', 'unverified', 'mapped')",
            name="ck_user_diagnoses_review",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["disease_id"], ["diseases.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_user_diagnoses_user_id", "user_diagnoses", ["user_id"])
    op.create_index(
        "uq_user_diagnoses_disease",
        "user_diagnoses",
        ["user_id", "disease_id"],
        unique=True,
        postgresql_where=sa.text("disease_id IS NOT NULL"),
    )
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_user_diagnoses_custom ON user_diagnoses "
            "(user_id, lower(custom_disease_name)) "
            "WHERE custom_disease_name IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_user_diagnoses_custom"))
    op.drop_index("uq_user_diagnoses_disease", table_name="user_diagnoses")
    op.drop_index("ix_user_diagnoses_user_id", table_name="user_diagnoses")
    op.drop_table("user_diagnoses")
    op.drop_index("uq_diseases_code", table_name="diseases")
    op.drop_index("ix_diseases_name", table_name="diseases")
    op.drop_index("ix_diseases_category_id", table_name="diseases")
    op.drop_table("diseases")
    op.drop_table("disease_categories")
    op.add_column("users", sa.Column("role", sa.String(32), nullable=True))
    op.execute(
        sa.text(
            "UPDATE users SET role = roles.code FROM roles WHERE roles.id = users.role_id"
        )
    )
    op.alter_column("users", "role", nullable=False)
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_column("users", "role_id")
    op.drop_table("roles")
