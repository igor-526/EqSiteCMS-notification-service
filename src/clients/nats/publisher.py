from uuid import UUID

from clients.nats.client import NatsJetstreamClient
from core.schemas.messaging import (
    MessagingBaseEventData,
    MessagingEvent,
    NotificationCommandSendEmailData,
    NotificationCommandSendVkData,
)
from settings import NatsSettings


class NatsEventPublisher:
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
    ) -> None:
        completed_headers = {
            "Nats-Msg-Id": str(event.event_id),
        }
        if headers is not None:
            completed_headers.update(headers)
        await self._client.publish(
            subject=event.event_subject, payload=payload.model_dump_json().encode("utf-8"), headers=completed_headers
        )


class NotificationCommandsSendEmailEventPublisher(NatsEventPublisher):
    def __init__(
        self,
        *,
        client: NatsJetstreamClient,
        settings: NatsSettings,
    ) -> None:
        super().__init__(
            client=client,
            settings=settings,
        )

    async def publish(self, *, payload: NotificationCommandSendEmailData, idempotency_key: UUID | None = None) -> UUID:
        event = MessagingEvent(
            event_id=idempotency_key or UUID(str(payload.event_uuid)),
            event_subject=self._settings.nats_subject_notification_commands_send_email,
        )
        await self._publish_event(event=event, payload=payload)
        return event.event_id


class NotificationCommandsSendVkEventPublisher(NatsEventPublisher):
    async def publish(self, *, payload: NotificationCommandSendVkData, idempotency_key: UUID | None = None) -> UUID:
        event = MessagingEvent(
            event_id=idempotency_key or payload.callback_request_id,
            event_subject=self._settings.nats_subject_notification_commands_send_vk,
        )
        await self._publish_event(event=event, payload=payload)
        return event.event_id
