from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.exceptions import NotFoundError
from core.services.notification_settings import NotificationSettingsService


@pytest.fixture
def dependencies() -> tuple[NotificationSettingsService, AsyncMock, AsyncMock, AsyncMock]:
    events, channels, settings = AsyncMock(), AsyncMock(), AsyncMock()
    return (
        NotificationSettingsService(event_repository=events, channel_repository=channels, setting_repository=settings),
        events,
        channels,
        settings,
    )


@pytest.mark.asyncio
async def test_read_returns_active_catalog_with_saved_state(dependencies) -> None:
    service, events, channels, settings = dependencies
    event = EventEntity(code="callback", name="Callback", is_active=True)
    channel = ChannelEntity(code="email", name="Email", is_active=True)
    events.get_active_events.return_value = [event]
    channels.get_active_channels.return_value = [channel]
    settings.get_by_tuple.return_value = object()

    result = await service.get_settings(user_id=uuid4())

    assert len(result) == 1 and result[0].enabled is True


@pytest.mark.asyncio
async def test_enable_and_disable_are_idempotent_commands(dependencies) -> None:
    service, events, channels, settings = dependencies
    event = EventEntity(code="callback", name="Callback", is_active=True)
    channel = ChannelEntity(code="email", name="Email", is_active=True)
    events.get_by_code.return_value = event
    channels.get_by_code.return_value = channel
    user_id = uuid4()

    enabled = await service.set_setting(user_id=user_id, event_code="callback", channel_code="email", enabled=True)
    disabled = await service.set_setting(user_id=user_id, event_code="callback", channel_code="email", enabled=False)

    assert enabled.enabled is True and disabled.enabled is False
    settings.enable.assert_awaited_once_with(user_id=user_id, event_id=event.id, channel_id=channel.id)
    settings.disable.assert_awaited_once_with(user_id=user_id, event_id=event.id, channel_id=channel.id)


@pytest.mark.asyncio
async def test_unknown_or_inactive_combination_is_rejected(dependencies) -> None:
    service, events, channels, settings = dependencies
    events.get_by_code.return_value = None
    channels.get_by_code.return_value = ChannelEntity(code="email", name="Email")

    with pytest.raises(NotFoundError):
        await service.set_setting(user_id=uuid4(), event_code="missing", channel_code="email", enabled=True)
    settings.enable.assert_not_awaited()
