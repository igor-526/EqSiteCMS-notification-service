from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import yaml  # type: ignore[import-untyped]

from clients.nats.client import NatsJetstreamClient
from clients.nats.consumers.callback_request import CallbackRequestConsumer
from clients.nats.handlers.callback_request import CallbackRequestHandler
from clients.nats.publisher import NotificationCommandsSendEmailEventPublisher
from core.protocols.messaging.handlers.callback_request import (
    CallbackRequestHandlerProtocol,
)
from core.schemas.messaging import CallbackRequestedData, NotificationCommandSendEmailData
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

    idempotency_key = uuid4()
    event_id = await publisher.publish(payload=payload, idempotency_key=idempotency_key)

    call = client.calls[0]
    decoded = NotificationCommandSendEmailData.model_validate_json(call["payload"])
    assert call["subject"] == "commands.notification.email.send"
    assert event_id == idempotency_key
    assert call["headers"] == {"Nats-Msg-Id": str(idempotency_key)}
    assert decoded == payload


def test_asyncapi_callback_contract_requires_equestrian_identity() -> None:
    document = (Path(__file__).parents[3] / "docs" / "asyncapi.yaml").read_text()

    assert "callback_request_id" in document
    assert "required: [occurred_at, equestrian_id, callback_request_id, phone]" in document
    assert "equestrian_id: {type: string, format: uuid}" in document
    assert "additionalProperties: false" in document


def test_backend_and_notification_asyncapi_callback_schemas_match() -> None:
    service_root = Path(__file__).parents[3]
    notification_document = yaml.safe_load((service_root / "docs" / "asyncapi.yaml").read_text())
    backend_document = yaml.safe_load((service_root.parent / "backend" / "docs" / "asyncapi.yaml").read_text())

    notification_schema = notification_document["components"]["schemas"]["CallbackRequestedPayload"]
    backend_schema = backend_document["components"]["schemas"]["CallbackRequestedPayload"]

    assert notification_schema == backend_schema


def test_callback_consumer_dto_accepts_valid_tenant_and_forbids_extra_fields() -> None:
    tenant_id = uuid4()
    callback_request_id = uuid4()
    dto = CallbackRequestedData.model_validate(
        {
            "equestrian_id": str(tenant_id),
            "callback_request_id": str(callback_request_id),
            "phone": "+70000000000",
        }
    )

    assert dto.equestrian_id == tenant_id
    with pytest.raises(ValueError):
        CallbackRequestedData.model_validate(
            {
                "equestrian_id": str(tenant_id),
                "callback_request_id": str(callback_request_id),
                "phone": "+70000000000",
                "unexpected": True,
            }
        )


@pytest.mark.asyncio
async def test_callback_handler_accepts_payload_with_tenant_identity() -> None:
    orchestrator = AsyncMock()
    handler = CallbackRequestHandler(orchestrator=orchestrator)
    callback_request_id = uuid4()
    equestrian_id = uuid4()

    await handler.handle(
        payload=(
            '{"occurred_at":"2026-08-24T12:00:00Z",'
            f'"equestrian_id":"{equestrian_id}",'
            f'"callback_request_id":"{callback_request_id}",'
            '"name":null,"comment":null,"phone":"+70000000000"}'
        ).encode(),
        headers={"Nats-Msg-Id": str(uuid4())},
    )

    orchestrator.process_event.assert_awaited_once_with(
        event_code="callback",
        payload={
            "callback_request_id": str(callback_request_id),
            "equestrian_id": str(equestrian_id),
            "name": None,
            "phone": "+70000000000",
            "comment": None,
        },
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"callback_request_id": str(uuid4()), "phone": "+70000000000"},
        {
            "equestrian_id": "not-a-uuid",
            "callback_request_id": str(uuid4()),
            "phone": "+70000000000",
        },
    ],
)
def test_callback_consumer_dto_rejects_missing_or_malformed_tenant(payload: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        CallbackRequestedData.model_validate(payload)


@pytest.mark.asyncio
async def test_callback_redelivery_preserves_tenant_and_correlation_boundaries() -> None:
    orchestrator = AsyncMock()
    handler = CallbackRequestHandler(orchestrator=orchestrator)
    tenant_id = uuid4()
    callback_request_id = uuid4()
    event = CallbackRequestedData(
        equestrian_id=tenant_id,
        callback_request_id=callback_request_id,
        phone="+70000000000",
    )

    await handler.handle(payload=event.model_dump_json().encode(), headers={})
    await handler.handle(payload=event.model_dump_json().encode(), headers={})

    assert orchestrator.process_event.await_count == 2
    for call in orchestrator.process_event.await_args_list:
        assert call.kwargs["payload"]["equestrian_id"] == str(tenant_id)
        assert call.kwargs["payload"]["callback_request_id"] == str(callback_request_id)


@pytest.mark.asyncio
async def test_callback_consumer_naks_service_update_failure_for_retry() -> None:
    handler = AsyncMock()
    handler.handle.side_effect = RuntimeError("service update failed")
    consumer = CallbackRequestConsumer(
        client=cast(NatsJetstreamClient, RecordingNatsClient()),
        settings=NatsSettings(),
        handler=cast(CallbackRequestHandlerProtocol, handler),
    )
    message = AsyncMock()
    message.headers = {"Nats-Msg-Id": str(uuid4())}
    message.data = b"{}"

    await consumer._process_message(message)

    message.nak.assert_awaited_once_with()
    message.ack.assert_not_awaited()
