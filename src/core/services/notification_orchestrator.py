import logging
from typing import Protocol
from uuid import UUID

from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.protocols.clients import EmailServiceClientProtocol, MainBackendClientProtocol
from core.protocols.messaging import (
    NotificationCommandSendEmailPublisherProtocol,
    NotificationCommandSendVkPublisherProtocol,
)
from core.schemas.messaging import NotificationCommandSendEmailData, NotificationCommandSendVkData
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
        enabled_user_ids: set[UUID],
    ) -> NotificationCommandSendEmailData | NotificationCommandSendVkData | None: ...


class NotificationOrchestratorService:
    def __init__(
        self,
        *,
        channel_repository: ChannelRepository,
        event_repository: EventRepository,
        user_setting_repository: UserNotificationSettingRepository,
        email_publisher: NotificationCommandSendEmailPublisherProtocol,
        vk_publisher: NotificationCommandSendVkPublisherProtocol,
        main_backend_client: MainBackendClientProtocol,
        email_service_client: EmailServiceClientProtocol,
    ) -> None:
        self._channel_repository = channel_repository
        self._event_repository = event_repository
        self._user_setting_repository = user_setting_repository
        self._email_publisher = email_publisher
        self._vk_publisher = vk_publisher
        self._main_backend_client = main_backend_client
        self._email_service_client = email_service_client
        self._handlers: dict[str, EventHandlerProtocol] = {}

    def register_handler(self, event_code: str, handler: EventHandlerProtocol) -> None:
        registered = self._handlers.get(event_code)
        if registered is handler:
            return
        if registered is not None:
            raise RuntimeError(f"Handler already registered for event: {event_code}")
        self._handlers[event_code] = handler

    async def process_event(
        self,
        *,
        event_code: str,
        payload: dict,
    ) -> None:
        correlation_id = payload.get("callback_request_id")
        logger.info(
            "Processing event: event_code=%s, correlation_id=%s",
            event_code,
            correlation_id,
        )

        # 1. Получить событие из БД по коду
        event = await self._event_repository.get_by_code(event_code)
        if not event:
            logger.warning("Event not found: event_code=%s", event_code)
            return

        if not event.is_active:
            logger.warning("Event is not active: event_code=%s", event_code)
            return

        # 2. Получить активные каналы
        channels = await self._channel_repository.get_active_channels()
        if not channels:
            logger.warning("No active channels found")
            return

        # 3. Получить настройки пользователей из БД
        user_settings = await self._user_setting_repository.get_users_by_event(event.id)
        if not user_settings:
            logger.warning("No user settings found for event: event_code=%s", event_code)

        # 4. Найти обработчик для события
        handler = self._handlers.get(event_code)
        if not handler:
            logger.warning("Handler not found for event: event_code=%s", event_code)
            return

        # 5. Для каждого канала сформировать и отправить уведомление
        published = False
        first_error: Exception | None = None
        for channel in channels:
            try:
                channel_published = await self._process_channel(
                    handler=handler,
                    channel=channel,
                    event=event,
                    payload=payload,
                    enabled_user_ids={
                        setting.user_id for setting in user_settings if setting.channel_id == channel.id
                    },
                )
                published = channel_published or published
            except Exception as exc:
                logger.exception("Channel processing failed: channel_code=%s", channel.code)
                first_error = first_error or exc

        if published and event_code == "callback":
            if not correlation_id:
                raise ValueError("callback_request_id is required for delivery confirmation")
            await self._main_backend_client.confirm_callback_delivery(callback_request_id=UUID(str(correlation_id)))
        if first_error is not None:
            raise first_error

    async def _process_channel(
        self,
        *,
        handler: EventHandlerProtocol,
        channel: ChannelEntity,
        event: EventEntity,
        payload: dict,
        enabled_user_ids: set[UUID],
    ) -> bool:
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
            enabled_user_ids=enabled_user_ids,
        )

        if not notification:
            logger.warning(
                "Handler returned no notification: channel_code=%s, correlation_id=%s",
                channel.code,
                payload.get("callback_request_id"),
            )
            return False

        # Отправить команду на доставку
        correlation_id = payload.get("callback_request_id")
        idempotency_key = UUID(str(correlation_id)) if correlation_id else None
        if channel.code == "email" and isinstance(notification, NotificationCommandSendEmailData):
            event_id = await self._email_publisher.publish(
                payload=notification,
                idempotency_key=idempotency_key,
            )
        elif channel.code == "vk" and isinstance(notification, NotificationCommandSendVkData):
            event_id = await self._vk_publisher.publish(
                payload=notification,
                idempotency_key=idempotency_key,
            )
        else:
            logger.error("Unsupported notification DTO: channel_code=%s", channel.code)
            return False
        logger.info(
            "Notification command published: event_id=%s, channel_code=%s, correlation_id=%s",
            event_id,
            channel.code,
            payload.get("callback_request_id"),
        )
        return True
