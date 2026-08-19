from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.services import NotificationSettingsService
from repositories import ChannelRepository, EventRepository, UserNotificationSettingRepository
from utils.database import get_session


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def get_notification_settings_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NotificationSettingsService:
    return NotificationSettingsService(
        event_repository=EventRepository(session),
        channel_repository=ChannelRepository(session),
        setting_repository=UserNotificationSettingRepository(session),
    )
