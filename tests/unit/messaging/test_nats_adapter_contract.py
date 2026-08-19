from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from clients.nats.client import NatsJetstreamClient
from clients.nats.consumers.callback_request import CallbackRequestConsumer
from clients.nats.publisher import NotificationCommandsSendEmailEventPublisher
from core.protocols.messaging.handlers.callback_request import (
    CallbackRequestHandlerProtocol,
)
from core.schemas.messaging import NotificationCommandSendEmailData
from settings import NatsSettings


def test_asyncapi_documents_canonical_runtime_subjects() -> None:
    document = (Path(__file__).parents[3] / "docs" / "asyncapi.yaml").read_text()
    settings = NatsSettings()

    assert f"  {settings.nats_subject_callback_requested}:" in document
    assert f"  {settings.nats_subject_notification_commands_send_email}:" in document
    assert "Nats-Msg-Id" in document
    assert "NotificationEmailPayload" in document


class RecordingNatsClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.jetstream = AsyncMock()

    async def publish(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class ContractCallbackRequestConsumer(CallbackRequestConsumer):
    async def _consume(self) -> None:
        return None


@pytest.mark.asyncio
async def test_notification_callback_consumer_uses_canonical_subject_stream_and_durable() -> None:
    client = RecordingNatsClient()
    client.jetstream.pull_subscribe.return_value = AsyncMock()
    consumer = ContractCallbackRequestConsumer(
        client=cast(NatsJetstreamClient, client),
        settings=NatsSettings(),
        handler=cast(CallbackRequestHandlerProtocol, AsyncMock()),
    )
    await consumer.start()

    client.jetstream.pull_subscribe.assert_awaited_once_with(
        subject="events.site.callback.requested",
        durable="notification-service-callback-requested",
        stream="SITE_EVENTS",
    )


@pytest.mark.asyncio
async def test_notification_email_publisher_matches_subject_headers_and_payload() -> None:
    client = RecordingNatsClient()
    publisher = NotificationCommandsSendEmailEventPublisher(
        client=cast(NatsJetstreamClient, client), settings=NatsSettings()
    )
    payload = NotificationCommandSendEmailData(
        event_uuid=uuid4(),
        to=["owner@example.com"],
        subject="Callback request",
        body="<p>Call back</p>",
    )

    event_id = await publisher.publish(payload=payload)

    call = client.calls[0]
    decoded = NotificationCommandSendEmailData.model_validate_json(call["payload"])
    assert call["subject"] == "commands.notification.email.send"
    assert call["headers"] == {"Nats-Msg-Id": str(event_id)}
    assert decoded == payload
