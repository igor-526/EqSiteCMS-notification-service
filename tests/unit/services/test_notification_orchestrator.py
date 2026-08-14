import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.services.notification_orchestrator import NotificationOrchestratorService


@pytest.fixture
def mock_channel_repository():
    return AsyncMock()


@pytest.fixture
def mock_event_repository():
    return AsyncMock()


@pytest.fixture
def mock_user_setting_repository():
    return AsyncMock()


@pytest.fixture
def mock_email_publisher():
    return AsyncMock()


@pytest.fixture
def orchestrator(
    mock_channel_repository,
    mock_event_repository,
    mock_user_setting_repository,
    mock_email_publisher,
):
    return NotificationOrchestratorService(
        channel_repository=mock_channel_repository,
        event_repository=mock_event_repository,
        user_setting_repository=mock_user_setting_repository,
        email_publisher=mock_email_publisher,
    )


@pytest.fixture
def sample_event():
    return EventEntity(
        id=uuid4(),
        code="callback",
        name="Обратный звонок",
        description="Обработка формы заявки на обратный звонок",
        metadata={"phone": {"required": True, "type": "phone_number"}},
        is_active=True,
    )


@pytest.fixture
def sample_channel():
    return ChannelEntity(
        id=uuid4(),
        code="email",
        name="Электронная почта",
        description="Доставка уведомлений на email",
        is_active=True,
    )


class TestNotificationOrchestrator:
    @pytest.mark.asyncio
    async def test_process_event_success(
        self,
        orchestrator,
        mock_event_repository,
        mock_channel_repository,
        mock_email_publisher,
        sample_event,
        sample_channel,
    ):
        mock_event_repository.get_by_code.return_value = sample_event
        mock_channel_repository.get_active_channels.return_value = [sample_channel]
        mock_email_publisher.publish.return_value = uuid4()

        # Регистрируем мок-обработчик
        mock_handler = AsyncMock()
        mock_handler.format_notification.return_value = MagicMock()
        orchestrator.register_handler("callback", mock_handler)

        await orchestrator.process_event(
            event_code="callback",
            payload={
                "callback_request_id": str(uuid4()),
                "name": "Test",
                "phone": "+79999999999",
                "comment": "Test comment",
                "equestrian_id": str(uuid4()),
            },
        )

        mock_event_repository.get_by_code.assert_called_once_with("callback")
        mock_channel_repository.get_active_channels.assert_called_once()
        mock_handler.format_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_event_not_found(
        self,
        orchestrator,
        mock_event_repository,
    ):
        mock_event_repository.get_by_code.return_value = None

        await orchestrator.process_event(
            event_code="nonexistent",
            payload={},
        )

        mock_event_repository.get_by_code.assert_called_once_with("nonexistent")

    @pytest.mark.asyncio
    async def test_process_event_inactive(
        self,
        orchestrator,
        mock_event_repository,
        sample_event,
    ):
        sample_event.is_active = False
        mock_event_repository.get_by_code.return_value = sample_event

        await orchestrator.process_event(
            event_code="callback",
            payload={},
        )

        mock_event_repository.get_by_code.assert_called_once_with("callback")

    @pytest.mark.asyncio
    async def test_process_event_no_channels(
        self,
        orchestrator,
        mock_event_repository,
        mock_channel_repository,
        sample_event,
    ):
        mock_event_repository.get_by_code.return_value = sample_event
        mock_channel_repository.get_active_channels.return_value = []

        await orchestrator.process_event(
            event_code="callback",
            payload={"equestrian_id": str(uuid4())},
        )

        mock_channel_repository.get_active_channels.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_event_no_handler(
        self,
        orchestrator,
        mock_event_repository,
        mock_channel_repository,
        sample_event,
        sample_channel,
    ):
        mock_event_repository.get_by_code.return_value = sample_event
        mock_channel_repository.get_active_channels.return_value = [sample_channel]

        await orchestrator.process_event(
            event_code="callback",
            payload={"equestrian_id": str(uuid4())},
        )

        # Не должен падать, просто залогирует warning
