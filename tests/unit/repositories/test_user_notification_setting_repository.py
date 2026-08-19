import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from repositories.user_notification_setting import UserNotificationSettingRepository


@pytest.mark.asyncio
async def test_concurrent_enable_uses_unique_tuple_conflict_guard() -> None:
    session = AsyncMock()
    repository = UserNotificationSettingRepository(session)
    user_id, event_id, channel_id = uuid4(), uuid4(), uuid4()

    await asyncio.gather(
        repository.enable(user_id=user_id, event_id=event_id, channel_id=channel_id),
        repository.enable(user_id=user_id, event_id=event_id, channel_id=channel_id),
    )

    statements = [str(call.args[0]) for call in session.execute.await_args_list]
    assert len(statements) == 2
    assert all("ON CONFLICT ON CONSTRAINT uq_user_action_channel DO NOTHING" in stmt for stmt in statements)


@pytest.mark.asyncio
async def test_disable_targets_only_owner_event_channel_tuple() -> None:
    session = AsyncMock()
    repository = UserNotificationSettingRepository(session)
    user_id, event_id, channel_id = uuid4(), uuid4(), uuid4()

    await repository.disable(user_id=user_id, event_id=event_id, channel_id=channel_id)

    statement = session.execute.await_args.args[0]
    params = statement.compile().params
    assert set(params.values()) == {user_id, event_id, channel_id}
    assert str(statement).count(" AND ") == 2


@pytest.mark.asyncio
async def test_enabled_ids_are_scoped_to_requested_candidates() -> None:
    session = AsyncMock()
    enabled_id = uuid4()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [enabled_id]
    session.execute.return_value = result
    repository = UserNotificationSettingRepository(session)

    ids = await repository.get_enabled_user_ids(event_id=uuid4(), channel_id=uuid4(), user_ids=[enabled_id, uuid4()])

    assert ids == {enabled_id}
