from sqlalchemy import Boolean, Column, String, Table

from utils.basemodel import metadata, timestamp_columns, uuid_pk

notification_channels = Table(
    "notification_channels",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("code", String(15), nullable=False, unique=True, index=True),
    Column("name", String(31), nullable=False),
    Column("description", String(511), nullable=True),
    Column("is_active", Boolean(), nullable=False, server_default="true"),
)
