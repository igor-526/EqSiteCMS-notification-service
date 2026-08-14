import logging
from typing import Protocol

from clients.email_service import EmailServiceClient
from clients.main_backend import MainBackendClient
from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.protocols.messaging import NotificationCommandSendEmailPublisherProtocol
from core.schemas.messaging import NotificationCommandSendEmailData
from repositories.channel import ChannelRepository
from repositories.event import EventRepository
from repositories.user_notification_setting import UserNotificationSettingRepository

logger = logging.getLogger(__name__)


class EventHandlerProtocol(Protocol):
    async def format_notification(
        self,
        *,
        channel_code: str,
        payload: dict,
        event: EventEntity,
    ) -> NotificationCommandSendEmailData | None: ...


class NotificationOrchestratorService:
    def __init__(
        self,
        *,
        channel_repository: ChannelRepository,
        event_repository: EventRepository,
        user_setting_repository: UserNotificationSettingRepository,
        email_publisher: NotificationCommandSendEmailPublisherProtocol,
        main_backend_client: MainBackendClient,
        email_service_client: EmailServiceClient,
    ) -> None:
        self._channel_repository = channel_repository
        self._event_repository = event_repository
        self._user_setting_repository = user_setting_repository
        self._email_publisher = email_publisher
        self._main_backend_client = main_backend_client
        self._email_service_client = email_service_client
        self._handlers: dict[str, EventHandlerProtocol] = {}

    def register_handler(self, event_code: str, handler: EventHandlerProtocol) -> None:
        self._handlers[event_code] = handler

    async def process_event(
        self,
        *,
        event_code: str,
        payload: dict,
    ) -> None:
        logger.info("Processing event: event_code=%s", event_code)

        # 1. Получить событие из БД по коду
        event = await self._event_repository.get_by_code(event_code)
        if not event:
            logger.warning("Event not found: event_code=%s", event_code)
            return

        if not event.is_active:
            logger.warning("Event is not active: event_code=%s", event_code)
            return

        # 2. Получить equestrian_id из payload
        equestrian_id = payload.get("equestrian_id")
        if not equestrian_id:
            logger.warning("equestrian_id not found in payload")
            return

        # 3. Получить активные каналы
        channels = await self._channel_repository.get_active_channels()
        if not channels:
            logger.warning("No active channels found")
            return

        # 4. Получить настройки пользователей из БД
        user_settings = await self._user_setting_repository.get_users_by_event(event.id)
        if not user_settings:
            logger.warning("No user settings found for event: event_code=%s", event_code)

        # 5. Найти обработчик для события
        handler = self._handlers.get(event_code)
        if not handler:
            logger.warning("Handler not found for event: event_code=%s", event_code)
            return

        # 6. Для каждого канала сформировать и отправить уведомление
        for channel in channels:
            await self._process_channel(
                handler=handler,
                channel=channel,
                event=event,
                payload=payload,
            )

    async def _process_channel(
        self,
        *,
        handler: EventHandlerProtocol,
        channel: ChannelEntity,
        event: EventEntity,
        payload: dict,
    ) -> None:
        logger.info(
            "Processing channel: channel_code=%s, event_code=%s",
            channel.code,
            event.code,
        )

        # Сформировать уведомление
        notification = await handler.format_notification(
            channel_code=channel.code,
            payload=payload,
            event=event,
        )

        if not notification:
            logger.warning(
                "Handler returned None for channel: channel_code=%s",
                channel.code,
            )
            return

        # Отправить команду на доставку
        event_id = await self._email_publisher.publish(payload=notification)
        logger.info(
            "Notification command published: event_id=%s, channel_code=%s",
            event_id,
            channel.code,
        )
