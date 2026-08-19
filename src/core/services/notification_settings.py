from uuid import UUID

from core.exceptions import NotFoundError
from core.schemas import NotificationSettingResponse
from repositories.channel import ChannelRepository
from repositories.event import EventRepository
from repositories.user_notification_setting import UserNotificationSettingRepository


class NotificationSettingsService:
    def __init__(
        self,
        *,
        event_repository: EventRepository,
        channel_repository: ChannelRepository,
        setting_repository: UserNotificationSettingRepository,
    ) -> None:
        self._event_repository = event_repository
        self._channel_repository = channel_repository
        self._setting_repository = setting_repository

    async def get_settings(self, *, user_id: UUID) -> list[NotificationSettingResponse]:
        events = await self._event_repository.get_active_events()
        channels = await self._channel_repository.get_active_channels()
        result: list[NotificationSettingResponse] = []
        for event in events:
            for channel in channels:
                setting = await self._setting_repository.get_by_tuple(
                    user_id=user_id, event_id=event.id, channel_id=channel.id
                )
                result.append(
                    NotificationSettingResponse(
                        user_id=user_id,
                        event_code=event.code,
                        event_name=event.name,
                        event_description=event.description,
                        channel_code=channel.code,
                        channel_name=channel.name,
                        enabled=setting is not None,
                    )
                )
        return result

    async def set_setting(
        self, *, user_id: UUID, event_code: str, channel_code: str, enabled: bool
    ) -> NotificationSettingResponse:
        event = await self._event_repository.get_by_code(event_code)
        channel = await self._channel_repository.get_by_code(channel_code)
        if event is None or not event.is_active or channel is None or not channel.is_active:
            raise NotFoundError("Active notification event/channel combination not found")
        if enabled:
            await self._setting_repository.enable(user_id=user_id, event_id=event.id, channel_id=channel.id)
        else:
            await self._setting_repository.disable(user_id=user_id, event_id=event.id, channel_id=channel.id)
        return NotificationSettingResponse(
            user_id=user_id,
            event_code=event.code,
            event_name=event.name,
            event_description=event.description,
            channel_code=channel.code,
            channel_name=channel.name,
            enabled=enabled,
        )
