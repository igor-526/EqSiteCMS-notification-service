from pydantic import Field

from core.entities.base import Entity, TimestampMixin


class EventEntity(Entity, TimestampMixin):
    code: str = Field(..., max_length=15)
    name: str = Field(..., max_length=31)
    description: str | None = Field(default=None, max_length=511)
    metadata: dict | None = Field(default=None)
    is_active: bool = Field(default=True)
