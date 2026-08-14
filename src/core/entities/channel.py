from pydantic import Field

from core.entities.base import Entity, TimestampMixin


class ChannelEntity(Entity, TimestampMixin):
    code: str = Field(..., max_length=15)
    name: str = Field(..., max_length=31)
    description: str | None = Field(default=None, max_length=511)
    is_active: bool = Field(default=True)
