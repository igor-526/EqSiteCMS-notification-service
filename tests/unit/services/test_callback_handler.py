from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from core.entities.event import EventEntity
from core.services.handlers.callback_handler import CallbackEventHandler


@pytest.fixture
def mock_main_backend_client():
    client = AsyncMock()
    # Mock admin user
    admin_user = MagicMock()
    admin_user.id = uuid4()
    client.get_users.return_value = MagicMock(items=[admin_user])
    return client


@pytest.fixture
def mock_email_service_client():
    client = AsyncMock()
    # Mock user email
    user_email = MagicMock()
    user_email.email = "igor-526@yandex.ru"
    user_email.user_id = None
    user_email.approved = True
    client.get_user_emails.return_value = [user_email]
    return client


@pytest.fixture
def handler(mock_main_backend_client, mock_email_service_client):
    return CallbackEventHandler(
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


class TestCallbackEventHandler:
    @pytest.mark.asyncio
    async def test_format_notification_email(
        self, handler, sample_event, mock_main_backend_client, mock_email_service_client
    ):
        payload = {
            "callback_request_id": str(uuid4()),
            "name": "Иван",
            "phone": "+79999999999",
            "comment": "Тестовый комментарий",
            "equestrian_id": str(uuid4()),
        }

        eligible_id = mock_main_backend_client.get_users.return_value.items[0].id
        mock_email_service_client.get_user_emails.return_value[0].user_id = eligible_id
        result = await handler.format_notification(
            channel_code="email",
            payload=payload,
            event=sample_event,
            enabled_user_ids={eligible_id},
        )

        assert result is not None
        assert result.to == ["igor-526@yandex.ru"]
        mock_main_backend_client.get_users.assert_awaited_once_with(role=["ADMIN", "SUPERUSER"])
        assert "запрос на обратный звонок" in result.subject.lower()
        assert "Иван" in result.body
        assert "+79999999999" in result.body

    @pytest.mark.asyncio
    async def test_format_notification_unsupported_channel(self, handler, sample_event):
        payload = {
            "callback_request_id": str(uuid4()),
            "name": "Иван",
            "phone": "+79999999999",
        }

        result = await handler.format_notification(
            channel_code="sms",
            payload=payload,
            event=sample_event,
            enabled_user_ids=set(),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_format_notification_missing_fields(
        self, handler, sample_event, mock_main_backend_client, mock_email_service_client
    ):
        payload = {}

        eligible_id = mock_main_backend_client.get_users.return_value.items[0].id
        mock_email_service_client.get_user_emails.return_value[0].user_id = eligible_id
        result = await handler.format_notification(
            channel_code="email",
            payload=payload,
            event=sample_event,
            enabled_user_ids={eligible_id},
        )

        assert result is not None
        assert "Не указано" in result.body
