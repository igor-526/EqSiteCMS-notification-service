from sqlalchemy import select

from core.entities.channel import ChannelEntity
from models import notification_channels
from repositories.base import AbstractRepository


class ChannelRepository(AbstractRepository[ChannelEntity]):
    table = notification_channels
    entity = ChannelEntity

    async def get_by_code(self, code: str) -> ChannelEntity | None:
        stmt = select(self.table).where(self.table.c.code == code)
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_active_channels(self) -> list[ChannelEntity]:
        stmt = select(self.table).where(self.table.c.is_active == True)  # noqa: E712
        rows = await self.session.execute(stmt)
        return [self.entity.model_validate(dict(row)) for row in rows.mappings().all()]
