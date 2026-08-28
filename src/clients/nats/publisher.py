import logging
from uuid import UUID

from clients.nats.client import NatsJetstreamClient
from core.schemas.messaging import (
    MessagingBaseEventData,
    MessagingEvent,
    NotificationCommandSendEmailData,
    NotificationCommandSendVkData,
    PublishedCommand,
    build_command_msg_id,
)
from settings import NatsSettings

logger = logging.getLogger(__name__)


class NatsEventPublisher:
    channel_code: str

    def __init__(
        self,
        *,
        client: NatsJetstreamClient,
        settings: NatsSettings,
    ) -> None:
        self._client = client
        self._settings = settings

    async def _publish_event(
        self, *, event: MessagingEvent, payload: MessagingBaseEventData, headers: dict[str, str] | None = None
    ) -> PublishedCommand:
        completed_headers = {
            "Nats-Msg-Id": str(event.event_id),
        }
        if headers is not None:
            completed_headers.update(headers)
        ack = await self._client.publish(
            subject=event.event_subject, payload=payload.model_dump_json().encode("utf-8"), headers=completed_headers
        )
        duplicate = bool(getattr(ack, "duplicate", False))
        if duplicate:
            logger.warning(
                "Notification command was deduplicated by broker: channel_code=%s, subject=%s, message_id=%s",
                self.channel_code,
                event.event_subject,
                event.event_id,
            )
        return PublishedCommand(message_id=event.event_id, duplicate=duplicate)


class NotificationCommandsSendEmailEventPublisher(NatsEventPublisher):
    channel_code = "email"

    async def publish(
        self, *, payload: NotificationCommandSendEmailData, idempotency_key: UUID | None = None
    ) -> PublishedCommand:
        event = MessagingEvent(
            event_id=build_command_msg_id(
                correlation_id=idempotency_key or UUID(str(payload.event_uuid)),
                channel_code=self.channel_code,
            ),
            event_subject=self._settings.nats_subject_notification_commands_send_email,
        )
        return await self._publish_event(event=event, payload=payload)


class NotificationCommandsSendVkEventPublisher(NatsEventPublisher):
    channel_code = "vk"

    async def publish(
        self, *, payload: NotificationCommandSendVkData, idempotency_key: UUID | None = None
    ) -> PublishedCommand:
        event = MessagingEvent(
            event_id=build_command_msg_id(
                correlation_id=idempotency_key or payload.callback_request_id,
                channel_code=self.channel_code,
            ),
            event_subject=self._settings.nats_subject_notification_commands_send_vk,
        )
        return await self._publish_event(event=event, payload=payload)
