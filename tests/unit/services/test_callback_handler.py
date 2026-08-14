import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from core.entities.event import EventEntity
from core.services.handlers.callback_handler import CallbackEventHandler


@pytest.fixture
def handler():
    return CallbackEventHandler()


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
    async def test_format_notification_email(self, handler, sample_event):
        payload = {
            "callback_request_id": str(uuid4()),
            "name": "Иван",
            "phone": "+79999999999",
            "comment": "Тестовый комментарий",
            "equestrian_id": str(uuid4()),
        }

        result = await handler.format_notification(
            channel_code="email",
            payload=payload,
            event=sample_event,
        )

        assert result is not None
        assert result.to == ["igor-526@yandex.ru"]
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
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_format_notification_missing_fields(self, handler, sample_event):
        payload = {}

        result = await handler.format_notification(
            channel_code="email",
            payload=payload,
            event=sample_event,
        )

        assert result is not None
        assert "Не указано" in result.body
