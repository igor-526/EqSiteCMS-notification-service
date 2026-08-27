from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

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
def mock_main_backend_client():
    return AsyncMock()


@pytest.fixture
def mock_email_service_client():
    return AsyncMock()


@pytest.fixture
def orchestrator(
    mock_channel_repository,
    mock_event_repository,
    mock_user_setting_repository,
    mock_email_publisher,
    mock_main_backend_client,
    mock_email_service_client,
):
    return NotificationOrchestratorService(
        channel_repository=mock_channel_repository,
        event_repository=mock_event_repository,
        user_setting_repository=mock_user_setting_repository,
        email_publisher=mock_email_publisher,
        main_backend_client=mock_main_backend_client,
        email_service_client=mock_email_service_client,
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
        setting = MagicMock(user_id=uuid4(), channel_id=sample_channel.id)
        orchestrator._user_setting_repository.get_users_by_event.return_value = [setting]

        # Регистрируем мок-обработчик
        mock_handler = AsyncMock()
        mock_handler.format_notification.return_value = MagicMock()
        orchestrator.register_handler("callback", mock_handler)

        callback_request_id = uuid4()
        equestrian_id = uuid4()
        await orchestrator.process_event(
            event_code="callback",
            payload={
                "callback_request_id": str(callback_request_id),
                "equestrian_id": str(equestrian_id),
                "name": "Test",
                "phone": "+79999999999",
                "comment": "Test comment",
            },
        )

        mock_event_repository.get_by_code.assert_called_once_with("callback")
        mock_channel_repository.get_active_channels.assert_called_once()
        mock_handler.format_notification.assert_called_once()
        assert mock_handler.format_notification.call_args.kwargs["enabled_user_ids"] == {setting.user_id}
        mock_email_publisher.publish.assert_awaited_once_with(
            payload=mock_handler.format_notification.return_value,
            idempotency_key=callback_request_id,
        )
        orchestrator._main_backend_client.confirm_callback_delivery.assert_awaited_once_with(
            callback_request_id=callback_request_id
        )

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
            payload={"callback_request_id": str(uuid4())},
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
            payload={"callback_request_id": str(uuid4())},
        )

        # Не должен падать, просто залогирует warning

    @pytest.mark.asyncio
    async def test_no_notification_does_not_confirm_delivery(
        self, orchestrator, mock_event_repository, mock_channel_repository, sample_event, sample_channel
    ):
        mock_event_repository.get_by_code.return_value = sample_event
        mock_channel_repository.get_active_channels.return_value = [sample_channel]
        orchestrator._user_setting_repository.get_users_by_event.return_value = []
        handler = AsyncMock()
        handler.format_notification.return_value = None
        orchestrator.register_handler("callback", handler)

        await orchestrator.process_event(
            event_code="callback",
            payload={"callback_request_id": str(uuid4()), "phone": "+70000000000"},
        )

        orchestrator._email_publisher.publish.assert_not_awaited()
        orchestrator._main_backend_client.confirm_callback_delivery.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_publish_error_does_not_confirm_delivery(
        self, orchestrator, mock_event_repository, mock_channel_repository, sample_event, sample_channel
    ):
        mock_event_repository.get_by_code.return_value = sample_event
        mock_channel_repository.get_active_channels.return_value = [sample_channel]
        orchestrator._user_setting_repository.get_users_by_event.return_value = []
        handler = AsyncMock()
        handler.format_notification.return_value = MagicMock()
        orchestrator.register_handler("callback", handler)
        orchestrator._email_publisher.publish.side_effect = RuntimeError("publish failed")

        with pytest.raises(RuntimeError, match="publish failed"):
            await orchestrator.process_event(
                event_code="callback",
                payload={"callback_request_id": str(uuid4()), "phone": "+70000000000"},
            )

        orchestrator._main_backend_client.confirm_callback_delivery.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_service_update_error_propagates_after_publish_for_retry(
        self, orchestrator, mock_event_repository, mock_channel_repository, sample_event, sample_channel
    ):
        callback_request_id = uuid4()
        mock_event_repository.get_by_code.return_value = sample_event
        mock_channel_repository.get_active_channels.return_value = [sample_channel]
        orchestrator._user_setting_repository.get_users_by_event.return_value = []
        handler = AsyncMock()
        handler.format_notification.return_value = MagicMock()
        orchestrator.register_handler("callback", handler)
        orchestrator._email_publisher.publish.return_value = callback_request_id
        orchestrator._main_backend_client.confirm_callback_delivery.side_effect = RuntimeError("service failed")

        with pytest.raises(RuntimeError, match="service failed"):
            await orchestrator.process_event(
                event_code="callback",
                payload={"callback_request_id": str(callback_request_id), "phone": "+70000000000"},
            )

        orchestrator._email_publisher.publish.assert_awaited_once_with(
            payload=handler.format_notification.return_value,
            idempotency_key=callback_request_id,
        )
