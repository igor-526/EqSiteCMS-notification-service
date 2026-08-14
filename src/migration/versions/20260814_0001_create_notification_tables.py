"""create notification tables

Revision ID: 20260814_0001
Revises: 20260710_0001
Create Date: 2026-08-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260814_0001"
down_revision: str | None = "20260710_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # notification_channels
    op.create_table(
        "notification_channels",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(15), nullable=False),
        sa.Column("name", sa.String(31), nullable=False),
        sa.Column("description", sa.String(511), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index("ix_notification_channels_code", "notification_channels", ["code"], unique=True)

    # notification_events
    op.create_table(
        "notification_events",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(15), nullable=False),
        sa.Column("name", sa.String(31), nullable=False),
        sa.Column("description", sa.String(511), nullable=True),
        sa.Column("metadata", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_index("ix_notification_events_code", "notification_events", ["code"], unique=True)

    # user_notification_settings
    op.create_table(
        "user_notification_settings",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action_id", UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["action_id"],
            ["notification_events.id"],
            name="fk_user_notification_settings_action_id_notification_events",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["notification_channels.id"],
            name="fk_user_notification_settings_channel_id_notification_channels",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "action_id", "channel_id", name="uq_user_action_channel"),
    )
    op.create_index("ix_user_notification_settings_user_id", "user_notification_settings", ["user_id"])
    op.create_index("ix_user_notification_settings_action_id", "user_notification_settings", ["action_id"])
    op.create_index("ix_user_notification_settings_channel_id", "user_notification_settings", ["channel_id"])


def downgrade() -> None:
    op.drop_table("user_notification_settings")
    op.drop_table("notification_events")
    op.drop_table("notification_channels")
