from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from clients.nats.client import NatsJetstreamClient
from clients.nats.publisher import NotificationCommandsSendVkEventPublisher
from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.schemas.messaging import (
    NotificationCommandSendEmailData,
    NotificationCommandSendVkData,
)
from core.services.handlers.callback_handler import CallbackEventHandler
from core.services.notification_orchestrator import NotificationOrchestratorService
from settings import NatsSettings


def vk_payload(**overrides: Any) -> dict[str, Any]:
    value = {
        "occurred_at": datetime(2026, 8, 27, tzinfo=UTC),
        "event_uuid": uuid4(),
        "callback_request_id": uuid4(),
        "user_ids": [uuid4()],
        "text": "Новый запрос",
    }
    value.update(overrides)
    return value


def test_ut01_vk_dto_accepts_canonical_payload() -> None:
    data = vk_payload()
    dto = NotificationCommandSendVkData.model_validate(data)
    assert dto.event_uuid == data["event_uuid"]
    assert dto.callback_request_id == data["callback_request_id"]


@pytest.mark.parametrize("missing", ["event_uuid", "callback_request_id"])
def test_ut02_vk_dto_requires_event_and_callback_identity(missing: str) -> None:
    data = vk_payload()
    del data[missing]
    with pytest.raises(ValidationError):
        NotificationCommandSendVkData.model_validate(data)


def test_ut03_vk_dto_rejects_empty_recipients() -> None:
    with pytest.raises(ValidationError):
        NotificationCommandSendVkData.model_validate(vk_payload(user_ids=[]))


def test_ut04_vk_dto_deduplicates_recipients() -> None:
    user_id = uuid4()
    assert NotificationCommandSendVkData.model_validate(vk_payload(user_ids=[user_id, user_id])).user_ids == [user_id]


@pytest.mark.parametrize("text", ["", "   ", "x" * 4097])
def test_ut05_vk_dto_rejects_invalid_text(text: str) -> None:
    with pytest.raises(ValidationError):
        NotificationCommandSendVkData.model_validate(vk_payload(text=text))


def test_ut06_vk_dto_forbids_extra_properties() -> None:
    with pytest.raises(ValidationError):
        NotificationCommandSendVkData.model_validate(vk_payload(vk_peer_id=123))


class RecordingNatsClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def publish(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_ut07_ut08_vk_publisher_uses_subject_and_callback_msg_id() -> None:
    client = RecordingNatsClient()
    publisher = NotificationCommandsSendVkEventPublisher(
        client=cast(NatsJetstreamClient, client), settings=NatsSettings()
    )
    payload = NotificationCommandSendVkData.model_validate(vk_payload())

    published_id = await publisher.publish(payload=payload, idempotency_key=payload.callback_request_id)

    assert client.calls[0]["subject"] == "commands.notification.vk.send"
    assert client.calls[0]["headers"] == {"Nats-Msg-Id": str(payload.callback_request_id)}
    assert published_id == payload.callback_request_id


def test_ut09_notification_asyncapi_vk_schema_matches_runtime_dto_shape() -> None:
    root = Path(__file__).parents[3]
    document = yaml.safe_load((root / "docs" / "asyncapi.yaml").read_text())
    schema = document["components"]["schemas"]["NotificationVkPayload"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"occurred_at", "event_uuid", "callback_request_id", "user_ids", "text"}
    assert schema["properties"]["user_ids"]["uniqueItems"] is True
    assert set(NotificationCommandSendVkData.model_fields) == set(schema["properties"])


def make_handler() -> tuple[CallbackEventHandler, AsyncMock, AsyncMock]:
    backend, email = AsyncMock(), AsyncMock()
    return CallbackEventHandler(main_backend_client=backend, email_service_client=email), backend, email


def callback_payload() -> dict[str, Any]:
    return {
        "occurred_at": datetime(2026, 8, 27, tzinfo=UTC),
        "callback_request_id": str(uuid4()),
        "equestrian_id": str(uuid4()),
        "name": None,
        "phone": "+70000000000",
        "comment": None,
    }


@pytest.mark.asyncio
async def test_ut10_ut11_ut12_vk_handler_intersects_tenant_roles_and_enabled_users() -> None:
    handler, backend, email = make_handler()
    admin_id, superuser_id, disabled_id = uuid4(), uuid4(), uuid4()
    backend.get_users.return_value = MagicMock(
        items=[MagicMock(id=admin_id), MagicMock(id=superuser_id), MagicMock(id=disabled_id)]
    )
    payload = callback_payload()

    result = await handler.format_notification(
        channel_code="vk",
        payload=payload,
        event=EventEntity(code="callback", name="Callback"),
        enabled_user_ids={admin_id, superuser_id},
    )

    assert isinstance(result, NotificationCommandSendVkData)
    assert set(result.user_ids) == {admin_id, superuser_id}
    backend.get_users.assert_awaited_once_with(
        equestrian_ids=[UUID(payload["equestrian_id"])], role=["ADMIN", "SUPERUSER"]
    )
    email.get_user_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut13_ut14_vk_handler_excludes_noneligible_and_foreign_users() -> None:
    handler, backend, _ = make_handler()
    eligible, non_admin, foreign_admin = uuid4(), uuid4(), uuid4()
    backend.get_users.return_value = MagicMock(items=[MagicMock(id=eligible)])
    result = await handler.format_notification(
        channel_code="vk",
        payload=callback_payload(),
        event=EventEntity(code="callback", name="Callback"),
        enabled_user_ids={eligible, non_admin, foreign_admin},
    )
    assert isinstance(result, NotificationCommandSendVkData)
    assert result.user_ids == [eligible]


@pytest.mark.asyncio
async def test_ut15_ut16_ut19_channel_preferences_and_formats_are_independent() -> None:
    handler, backend, email = make_handler()
    user_id = uuid4()
    backend.get_users.return_value = MagicMock(items=[MagicMock(id=user_id)])
    email.get_user_emails.return_value = [MagicMock(user_id=user_id, email="owner@example.test", approved=True)]
    payload = callback_payload()
    event = EventEntity(code="callback", name="Callback")

    email_command = await handler.format_notification(
        channel_code="email", payload=payload, event=event, enabled_user_ids={user_id}
    )
    vk_command = await handler.format_notification(
        channel_code="vk", payload=payload, event=event, enabled_user_ids={user_id}
    )

    assert isinstance(email_command, NotificationCommandSendEmailData)
    assert isinstance(vk_command, NotificationCommandSendVkData)
    assert "<html>" in email_command.body
    assert "<html>" not in vk_command.text
    assert payload["callback_request_id"] not in vk_command.text
    assert payload["equestrian_id"] not in vk_command.text


@pytest.mark.asyncio
async def test_ut17_empty_vk_recipient_set_returns_no_command() -> None:
    handler, backend, email = make_handler()
    result = await handler.format_notification(
        channel_code="vk",
        payload=callback_payload(),
        event=EventEntity(code="callback", name="Callback"),
        enabled_user_ids=set(),
    )
    assert result is None
    backend.get_users.assert_not_awaited()
    email.get_user_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut18_vk_user_lookup_error_is_fail_closed() -> None:
    handler, backend, _ = make_handler()
    backend.get_users.side_effect = TimeoutError("backend unavailable")
    assert (
        await handler.format_notification(
            channel_code="vk",
            payload=callback_payload(),
            event=EventEntity(code="callback", name="Callback"),
            enabled_user_ids={uuid4()},
        )
        is None
    )


def make_orchestrator(
    channels: list[ChannelEntity],
) -> tuple[NotificationOrchestratorService, AsyncMock, AsyncMock, AsyncMock]:
    channel_repository, event_repository, setting_repository = AsyncMock(), AsyncMock(), AsyncMock()
    email_publisher, vk_publisher, backend = AsyncMock(), AsyncMock(), AsyncMock()
    event = EventEntity(code="callback", name="Callback", is_active=True)
    event_repository.get_by_code.return_value = event
    channel_repository.get_active_channels.return_value = channels
    setting_repository.get_users_by_event.return_value = []
    service = NotificationOrchestratorService(
        channel_repository=channel_repository,
        event_repository=event_repository,
        user_setting_repository=setting_repository,
        email_publisher=email_publisher,
        vk_publisher=vk_publisher,
        main_backend_client=backend,
        email_service_client=AsyncMock(),
    )
    return service, email_publisher, vk_publisher, backend


@pytest.mark.asyncio
async def test_ut20_unknown_channel_uses_no_publisher() -> None:
    channel = ChannelEntity(code="sms", name="SMS")
    service, email_publisher, vk_publisher, _ = make_orchestrator([channel])
    handler = AsyncMock()
    handler.format_notification.return_value = None
    service.register_handler("callback", handler)
    await service.process_event(event_code="callback", payload={"callback_request_id": str(uuid4())})
    email_publisher.publish.assert_not_awaited()
    vk_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_ut20_channel_dto_mismatch_uses_no_publisher() -> None:
    service, email_publisher, vk_publisher, _ = make_orchestrator([ChannelEntity(code="vk", name="VK")])
    handler = AsyncMock()
    handler.format_notification.return_value = NotificationCommandSendEmailData(
        event_uuid=uuid4(), to=["owner@example.test"], subject="Callback", body="Body"
    )
    service.register_handler("callback", handler)

    await service.process_event(event_code="callback", payload={"callback_request_id": str(uuid4())})

    email_publisher.publish.assert_not_awaited()
    vk_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["email", "vk"])
async def test_ut21_ut22_single_channel_puback_confirms_delivery(kind: str) -> None:
    channel = ChannelEntity(code=kind, name=kind)
    service, email_publisher, vk_publisher, backend = make_orchestrator([channel])
    callback_id = uuid4()
    handler = AsyncMock()
    if kind == "email":
        handler.format_notification.return_value = NotificationCommandSendEmailData(
            event_uuid=uuid4(), to=["owner@example.test"], subject="Callback", body="Body"
        )
    else:
        handler.format_notification.return_value = NotificationCommandSendVkData.model_validate(
            vk_payload(callback_request_id=callback_id)
        )
    service.register_handler("callback", handler)
    await service.process_event(event_code="callback", payload={"callback_request_id": str(callback_id)})
    expected, unexpected = (email_publisher, vk_publisher) if kind == "email" else (vk_publisher, email_publisher)
    expected.publish.assert_awaited_once()
    unexpected.publish.assert_not_awaited()
    backend.confirm_callback_delivery.assert_awaited_once_with(callback_request_id=callback_id)


@pytest.mark.asyncio
async def test_ut23_two_pubacks_produce_one_confirmation() -> None:
    email_channel = ChannelEntity(code="email", name="Email")
    vk_channel = ChannelEntity(code="vk", name="VK")
    service, email_publisher, vk_publisher, backend = make_orchestrator([email_channel, vk_channel])
    callback_id = uuid4()
    handler = AsyncMock()
    handler.format_notification.side_effect = [
        NotificationCommandSendEmailData(event_uuid=uuid4(), to=["a@example.test"], subject="S", body="B"),
        NotificationCommandSendVkData.model_validate(vk_payload(callback_request_id=callback_id)),
    ]
    service.register_handler("callback", handler)
    await service.process_event(event_code="callback", payload={"callback_request_id": str(callback_id)})
    email_publisher.publish.assert_awaited_once()
    vk_publisher.publish.assert_awaited_once()
    backend.confirm_callback_delivery.assert_awaited_once_with(callback_request_id=callback_id)


@pytest.mark.asyncio
async def test_ut24_no_puback_produces_no_confirmation() -> None:
    service, _, _, backend = make_orchestrator([ChannelEntity(code="vk", name="VK")])
    handler = AsyncMock()
    handler.format_notification.return_value = None
    service.register_handler("callback", handler)
    await service.process_event(event_code="callback", payload={"callback_request_id": str(uuid4())})
    backend.confirm_callback_delivery.assert_not_awaited()
