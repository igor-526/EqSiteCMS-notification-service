from sqlalchemy import select

from core.entities.event import EventEntity
from models import notification_events
from repositories.base import AbstractRepository


class EventRepository(AbstractRepository[EventEntity]):
    table = notification_events
    entity = EventEntity

    async def get_by_code(self, code: str) -> EventEntity | None:
        stmt = select(self.table).where(self.table.c.code == code)
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_active_events(self) -> list[EventEntity]:
        stmt = select(self.table).where(self.table.c.is_active == True)  # noqa: E712
        rows = await self.session.execute(stmt)
        return [self.entity.model_validate(dict(row)) for row in rows.mappings().all()]
