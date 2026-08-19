from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

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

    async def get_by_tuple(
        self, *, user_id: UUID, event_id: UUID, channel_id: UUID
    ) -> UserNotificationSettingEntity | None:
        stmt = select(self.table).where(
            self.table.c.user_id == user_id,
            self.table.c.action_id == event_id,
            self.table.c.channel_id == channel_id,
        )
        row = (await self.session.execute(stmt)).mappings().first()
        return self.entity.model_validate(dict(row)) if row is not None else None

    async def enable(self, *, user_id: UUID, event_id: UUID, channel_id: UUID) -> None:
        stmt = (
            insert(self.table)
            .values(user_id=user_id, action_id=event_id, channel_id=channel_id)
            .on_conflict_do_nothing(constraint="uq_user_action_channel")
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def disable(self, *, user_id: UUID, event_id: UUID, channel_id: UUID) -> None:
        stmt = delete(self.table).where(
            self.table.c.user_id == user_id,
            self.table.c.action_id == event_id,
            self.table.c.channel_id == channel_id,
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def get_enabled_user_ids(self, *, event_id: UUID, channel_id: UUID, user_ids: Sequence[UUID]) -> set[UUID]:
        if not user_ids:
            return set()
        stmt = select(self.table.c.user_id).where(
            self.table.c.action_id == event_id,
            self.table.c.channel_id == channel_id,
            self.table.c.user_id.in_(user_ids),
        )
        return set((await self.session.execute(stmt)).scalars().all())
