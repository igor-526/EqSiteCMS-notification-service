from uuid import UUID

from sqlalchemy import select

from core.entities.base import Entity, TimestampMixin
from models import user_notification_settings
from repositories.base import AbstractRepository


class UserNotificationSettingEntity(Entity, TimestampMixin):
    user_id: UUID
    action_id: UUID
    channel_id: UUID


class UserNotificationSettingRepository(AbstractRepository[UserNotificationSettingEntity]):
    table = user_notification_settings
    entity = UserNotificationSettingEntity

    async def get_by_user_and_event(self, user_id: UUID, action_id: UUID) -> list[UserNotificationSettingEntity]:
        stmt = select(self.table).where(
            self.table.c.user_id == user_id,
            self.table.c.action_id == action_id,
        )
        rows = await self.session.execute(stmt)
        return [self.entity.model_validate(dict(row)) for row in rows.mappings().all()]

    async def get_users_by_event(self, action_id: UUID) -> list[UserNotificationSettingEntity]:
        stmt = select(self.table).where(self.table.c.action_id == action_id)
        rows = await self.session.execute(stmt)
        return [self.entity.model_validate(dict(row)) for row in rows.mappings().all()]
