from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from dependency_injector import providers

from containers.application import ApplicationContainer, wire_event_handlers
from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.schemas.messaging import PublishedCommand


@pytest.mark.asyncio
async def test_production_container_wires_single_callback_path_and_publishes() -> None:
    container = ApplicationContainer()
    event = EventEntity(code="callback", name="Callback", is_active=True)
    channel = ChannelEntity(code="email", name="Email", is_active=True)
    recipient_id = uuid4()

    event_repository = AsyncMock()
    event_repository.get_by_code.return_value = event
    channel_repository = AsyncMock()
    channel_repository.get_active_channels.return_value = [channel]
    setting_repository = AsyncMock()
    setting_repository.get_users_by_event.return_value = [MagicMock(user_id=recipient_id, channel_id=channel.id)]
    backend_client = AsyncMock()
    backend_client.get_users.return_value = MagicMock(items=[MagicMock(id=recipient_id)])
    email_client = AsyncMock()
    email_client.get_user_emails.return_value = [
        MagicMock(user_id=recipient_id, email="eligible@example.com", approved=True)
    ]
    publisher = AsyncMock()
    publisher.publish.return_value = PublishedCommand(message_id=uuid4(), duplicate=False)

    container.event_repository.override(providers.Object(event_repository))
    container.channel_repository.override(providers.Object(channel_repository))
    container.user_notification_setting_repository.override(providers.Object(setting_repository))
    container.main_backend_client.override(providers.Object(backend_client))
    container.email_service_client.override(providers.Object(email_client))
    container.notification_commands_send_email_publisher.override(providers.Object(publisher))

    orchestrator = wire_event_handlers(container)
    assert wire_event_handlers(container) is orchestrator
    assert orchestrator._handlers == {"callback": container.callback_event_handler()}

    callback_request_id = uuid4()
    equestrian_id = uuid4()
    await orchestrator.process_event(
        event_code="callback",
        payload={
            "callback_request_id": str(callback_request_id),
            "equestrian_id": str(equestrian_id),
            "phone": "+70000000000",
        },
    )

    publisher.publish.assert_awaited_once()
    command = publisher.publish.await_args.kwargs["payload"]
    assert command.to == ["eligible@example.com"]
    backend_client.get_users.assert_awaited_once_with(equestrian_ids=[equestrian_id], role=["ADMIN", "SUPERUSER"])
    backend_client.confirm_callback_delivery.assert_awaited_once_with(callback_request_id=callback_request_id)
