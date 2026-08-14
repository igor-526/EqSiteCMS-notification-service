from uuid import UUID

from clients.nats.client import NatsJetstreamClient
from core.schemas.messaging import MessagingBaseEventData, MessagingEvent, NotificationCommandSendEmailData
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

    async def publish(self, *, payload: NotificationCommandSendEmailData) -> UUID:
        event = MessagingEvent(event_subject=self._settings.nats_subject_notification_commands_send_email)
        await self._publish_event(event=event, payload=payload)
        return event.event_id
