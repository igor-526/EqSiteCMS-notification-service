import logging
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from clients.nats.client import NatsJetstreamClient
from clients.nats.publisher import (
    NotificationCommandsSendEmailEventPublisher,
    NotificationCommandsSendVkEventPublisher,
)
from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.schemas.messaging import (
    NotificationCommandSendEmailData,
    NotificationCommandSendVkData,
    build_command_msg_id,
)
from core.services.notification_orchestrator import NotificationOrchestratorService
from settings import NatsSettings

# Фиксированный тестовый вектор. Идентичный вектор проверяется в vk-service:
# tests/unit/messaging/test_command_identity.py — расхождение означает рассинхронизацию контракта.
VECTOR_CALLBACK_ID = UUID("e317a8b9-5513-437b-ae2a-abb0a8883ca8")
VECTOR_EMAIL_MSG_ID = UUID("0a08d7c9-ac68-5c4f-8e7a-7c30d3c8c1d4")
VECTOR_VK_MSG_ID = UUID("aacfe433-467a-5b34-812d-165f7773589d")


class RecordingNatsClient:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self._duplicate = duplicate

    async def publish(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return type("PubAck", (), {"duplicate": self._duplicate})()


def email_command() -> NotificationCommandSendEmailData:
    return NotificationCommandSendEmailData(
        event_uuid=uuid4(), to=["owner@example.test"], subject="Callback", body="Body"
    )


def vk_command(callback_request_id: UUID) -> NotificationCommandSendVkData:
    return NotificationCommandSendVkData(
        event_uuid=uuid4(),
        callback_request_id=callback_request_id,
        user_ids=[uuid4()],
        text="Новый запрос",
    )


def make_publishers(
    client: RecordingNatsClient,
) -> tuple[NotificationCommandsSendEmailEventPublisher, NotificationCommandsSendVkEventPublisher]:
    settings = NatsSettings()
    typed = cast(NatsJetstreamClient, client)
    return (
        NotificationCommandsSendEmailEventPublisher(client=typed, settings=settings),
        NotificationCommandsSendVkEventPublisher(client=typed, settings=settings),
    )


def test_msg_id_matches_fixed_vector() -> None:
    assert build_command_msg_id(correlation_id=VECTOR_CALLBACK_ID, channel_code="email") == VECTOR_EMAIL_MSG_ID
    assert build_command_msg_id(correlation_id=VECTOR_CALLBACK_ID, channel_code="vk") == VECTOR_VK_MSG_ID


def test_msg_id_is_stable_across_recomputation() -> None:
    callback_id = uuid4()
    assert build_command_msg_id(correlation_id=callback_id, channel_code="vk") == build_command_msg_id(
        correlation_id=callback_id, channel_code="vk"
    )


def test_msg_id_differs_between_channels_of_one_callback() -> None:
    callback_id = uuid4()
    assert build_command_msg_id(correlation_id=callback_id, channel_code="email") != build_command_msg_id(
        correlation_id=callback_id, channel_code="vk"
    )


async def test_email_and_vk_publishers_emit_different_msg_ids_for_one_callback() -> None:
    client = RecordingNatsClient()
    email_publisher, vk_publisher = make_publishers(client)
    callback_id = uuid4()

    email_published = await email_publisher.publish(payload=email_command(), idempotency_key=callback_id)
    vk_published = await vk_publisher.publish(payload=vk_command(callback_id), idempotency_key=callback_id)

    email_header = client.calls[0]["headers"]["Nats-Msg-Id"]
    vk_header = client.calls[1]["headers"]["Nats-Msg-Id"]
    assert email_header != vk_header
    assert email_header == str(email_published.message_id)
    assert vk_header == str(vk_published.message_id)
    assert email_header != str(callback_id)
    assert vk_header != str(callback_id)


async def test_publisher_msg_id_is_stable_between_reprocessings() -> None:
    client = RecordingNatsClient()
    _, vk_publisher = make_publishers(client)
    callback_id = uuid4()

    first = await vk_publisher.publish(payload=vk_command(callback_id), idempotency_key=callback_id)
    second = await vk_publisher.publish(payload=vk_command(callback_id), idempotency_key=callback_id)

    assert first.message_id == second.message_id


async def test_publisher_reports_broker_duplicate() -> None:
    client = RecordingNatsClient(duplicate=True)
    _, vk_publisher = make_publishers(client)

    published = await vk_publisher.publish(payload=vk_command(uuid4()), idempotency_key=uuid4())

    assert published.duplicate is True


async def test_publisher_reports_new_message() -> None:
    client = RecordingNatsClient()
    _, vk_publisher = make_publishers(client)

    published = await vk_publisher.publish(payload=vk_command(uuid4()), idempotency_key=uuid4())

    assert published.duplicate is False


def make_orchestrator(
    channels: list[ChannelEntity],
) -> tuple[NotificationOrchestratorService, AsyncMock, AsyncMock]:
    channel_repository, event_repository, setting_repository = AsyncMock(), AsyncMock(), AsyncMock()
    vk_publisher, backend = AsyncMock(), AsyncMock()
    event_repository.get_by_code.return_value = EventEntity(code="callback", name="Callback", is_active=True)
    channel_repository.get_active_channels.return_value = channels
    setting_repository.get_users_by_event.return_value = []
    service = NotificationOrchestratorService(
        channel_repository=channel_repository,
        event_repository=event_repository,
        user_setting_repository=setting_repository,
        email_publisher=AsyncMock(),
        vk_publisher=vk_publisher,
        main_backend_client=backend,
        email_service_client=AsyncMock(),
    )
    return service, vk_publisher, backend


async def test_duplicate_puback_is_idempotent_success(caplog: pytest.LogCaptureFixture) -> None:
    service, vk_publisher, backend = make_orchestrator([ChannelEntity(code="vk", name="VK")])
    callback_id = uuid4()
    command = vk_command(callback_id)
    message_id = build_command_msg_id(correlation_id=callback_id, channel_code="vk")
    vk_publisher.publish.return_value = type("PublishedCommand", (), {"message_id": message_id, "duplicate": True})()
    handler = AsyncMock()
    handler.format_notification.return_value = command
    service.register_handler("callback", handler)

    with caplog.at_level(logging.WARNING):
        await service.process_event(event_code="callback", payload={"callback_request_id": str(callback_id)})

    backend.confirm_callback_delivery.assert_awaited_once_with(callback_request_id=callback_id)
    assert vk_publisher.publish.await_count == 1
    assert any(
        record.levelno >= logging.WARNING and str(callback_id) in record.getMessage() for record in caplog.records
    )
