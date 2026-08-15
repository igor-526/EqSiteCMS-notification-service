from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from core.entities.event import EventEntity
from repositories.event import EventRepository


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def event_repository(mock_session):
    return EventRepository(session=mock_session)


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


class TestEventRepository:
    @pytest.mark.asyncio
    async def test_get_by_code_found(self, event_repository, mock_session, sample_event):
        mock_mapping = MagicMock()
        mock_mapping.__iter__ = MagicMock(
            return_value=iter(
                {
                    "id": sample_event.id,
                    "code": sample_event.code,
                    "name": sample_event.name,
                    "description": sample_event.description,
                    "metadata": sample_event.metadata,
                    "is_active": sample_event.is_active,
                    "created_at": sample_event.created_at,
                    "updated_at": sample_event.updated_at,
                }.items()
            )
        )

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_mapping
        mock_session.execute.return_value = mock_result

        with patch.object(EventEntity, "model_validate", return_value=sample_event):
            result = await event_repository.get_by_code("callback")

        assert result is not None
        assert result.code == "callback"

    @pytest.mark.asyncio
    async def test_get_by_code_not_found(self, event_repository, mock_session):
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        result = await event_repository.get_by_code("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_events(self, event_repository, mock_session, sample_event):
        mock_mapping = MagicMock()
        mock_mapping.__iter__ = MagicMock(
            return_value=iter(
                {
                    "id": sample_event.id,
                    "code": sample_event.code,
                    "name": sample_event.name,
                    "description": sample_event.description,
                    "metadata": sample_event.metadata,
                    "is_active": True,
                    "created_at": sample_event.created_at,
                    "updated_at": sample_event.updated_at,
                }.items()
            )
        )

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [mock_mapping]
        mock_session.execute.return_value = mock_result

        with patch.object(EventEntity, "model_validate", return_value=sample_event):
            result = await event_repository.get_active_events()

        assert len(result) == 1
        assert result[0].is_active is True

    @pytest.mark.asyncio
    async def test_get_active_events_empty(self, event_repository, mock_session):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await event_repository.get_active_events()

        assert len(result) == 0
