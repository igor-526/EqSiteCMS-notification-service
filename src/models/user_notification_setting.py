from sqlalchemy import Column, ForeignKey, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from utils.basemodel import metadata, timestamp_columns, uuid_pk

user_notification_settings = Table(
    "user_notification_settings",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
    Column(
        "action_id",
        UUID(as_uuid=True),
        ForeignKey("notification_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "channel_id",
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    UniqueConstraint("user_id", "action_id", "channel_id", name="uq_user_action_channel"),
)
