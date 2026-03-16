"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable uuid-ossp extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ------------------------------------------------------------------ #
    # projects                                                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("delivery_url", sa.Text(), nullable=False),
        sa.Column("zip_url", sa.Text(), nullable=True),
        sa.Column("email_uid", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="new", nullable=False),
        sa.Column("error_stage", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("email_uid"),
    )
    op.create_index("idx_projects_status", "projects", ["status"])
    op.create_index("idx_projects_tenant_id", "projects", ["tenant_id"])

    # ------------------------------------------------------------------ #
    # photos                                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "photos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("dropbox_path", sa.Text(), nullable=True),
        sa.Column("room_tag", sa.Text(), nullable=True),
        sa.Column(
            "feature_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'"),
            nullable=True,
        ),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("selected_rank", sa.Integer(), nullable=True),
        sa.Column("hero_slot", sa.Text(), nullable=True),
        sa.Column("is_best_available", sa.Boolean(), server_default="false", nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_photos_project_id", "photos", ["project_id"])
    op.create_index(
        "idx_photos_selected_rank",
        "photos",
        ["project_id", "selected_rank"],
    )
    op.create_index(
        "idx_photos_room_tag",
        "photos",
        ["project_id", "room_tag", sa.text("ai_score DESC")],
    )

    # ------------------------------------------------------------------ #
    # processed_emails                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "processed_emails",
        sa.Column("email_uid", sa.Text(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "processed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("email_uid"),
    )
    op.create_index("idx_processed_emails_uid", "processed_emails", ["email_uid"])


def downgrade() -> None:
    op.drop_index("idx_processed_emails_uid", table_name="processed_emails")
    op.drop_table("processed_emails")

    op.drop_index("idx_photos_room_tag", table_name="photos")
    op.drop_index("idx_photos_selected_rank", table_name="photos")
    op.drop_index("idx_photos_project_id", table_name="photos")
    op.drop_table("photos")

    op.drop_index("idx_projects_tenant_id", table_name="projects")
    op.drop_index("idx_projects_status", table_name="projects")
    op.drop_table("projects")
