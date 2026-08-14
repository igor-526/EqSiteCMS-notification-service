from sqlalchemy import JSON, Boolean, Column, String, Table

from utils.basemodel import metadata, timestamp_columns, uuid_pk

notification_events = Table(
    "notification_events",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("code", String(15), nullable=False, unique=True, index=True),
    Column("name", String(31), nullable=False),
    Column("description", String(511), nullable=True),
    Column("metadata", JSON, nullable=True),
    Column("is_active", Boolean(), nullable=False, server_default="true"),
)
