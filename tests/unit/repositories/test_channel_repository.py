from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from core.entities.channel import ChannelEntity
from repositories.channel import ChannelRepository


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def channel_repository(mock_session):
    return ChannelRepository(session=mock_session)


@pytest.fixture
def sample_channel():
    return ChannelEntity(
        id=uuid4(),
        code="email",
        name="Электронная почта",
        description="Доставка уведомлений на email",
        is_active=True,
    )


class TestChannelRepository:
    @pytest.mark.asyncio
    async def test_get_by_code_found(self, channel_repository, mock_session, sample_channel):
        mock_mapping = MagicMock()
        mock_mapping.__iter__ = MagicMock(
            return_value=iter(
                {
                    "id": sample_channel.id,
                    "code": sample_channel.code,
                    "name": sample_channel.name,
                    "description": sample_channel.description,
                    "is_active": sample_channel.is_active,
                    "created_at": sample_channel.created_at,
                    "updated_at": sample_channel.updated_at,
                }.items()
            )
        )

        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = mock_mapping
        mock_session.execute.return_value = mock_result

        with patch.object(ChannelEntity, "model_validate", return_value=sample_channel):
            result = await channel_repository.get_by_code("email")

        assert result is not None
        assert result.code == "email"

    @pytest.mark.asyncio
    async def test_get_by_code_not_found(self, channel_repository, mock_session):
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result

        result = await channel_repository.get_by_code("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_channels(self, channel_repository, mock_session, sample_channel):
        mock_mapping = MagicMock()
        mock_mapping.__iter__ = MagicMock(
            return_value=iter(
                {
                    "id": sample_channel.id,
                    "code": sample_channel.code,
                    "name": sample_channel.name,
                    "description": sample_channel.description,
                    "is_active": True,
                    "created_at": sample_channel.created_at,
                    "updated_at": sample_channel.updated_at,
                }.items()
            )
        )

        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [mock_mapping]
        mock_session.execute.return_value = mock_result

        with patch.object(ChannelEntity, "model_validate", return_value=sample_channel):
            result = await channel_repository.get_active_channels()

        assert len(result) == 1
        assert result[0].is_active is True

    @pytest.mark.asyncio
    async def test_get_active_channels_empty(self, channel_repository, mock_session):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await channel_repository.get_active_channels()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_active_channels_is_ordered_by_code(self, channel_repository, mock_session):
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await channel_repository.get_active_channels()

        statement = mock_session.execute.await_args.args[0]
        assert "ORDER BY notification_channels.code" in str(statement)
