import asyncio
import logging
from typing import cast
from unittest.mock import AsyncMock

import pytest

from clients.nats.client import NatsJetstreamClient
from clients.nats.consumers.callback_request import CallbackRequestConsumer
from core.protocols.messaging.handlers.callback_request import (
    CallbackRequestHandlerProtocol,
)
from settings import NatsSettings


def make_consumer(*, fetch_side_effect: list[object]) -> tuple[CallbackRequestConsumer, AsyncMock, AsyncMock]:
    subscription = AsyncMock()
    subscription.fetch.side_effect = fetch_side_effect
    handler = AsyncMock()
    consumer = CallbackRequestConsumer(
        client=cast(NatsJetstreamClient, AsyncMock()),
        settings=NatsSettings(),
        handler=cast(CallbackRequestHandlerProtocol, handler),
    )
    consumer._subscription = subscription
    return consumer, subscription, handler


async def test_builtin_idle_timeout_starts_next_fetch_and_preserves_cancellation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    consumer, subscription, _ = make_consumer(
        fetch_side_effect=[TimeoutError(), asyncio.CancelledError()],
    )

    with caplog.at_level(logging.WARNING), pytest.raises(asyncio.CancelledError):
        await consumer._consume()

    assert subscription.fetch.await_count == 2
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


async def test_message_after_builtin_idle_timeout_is_handled_and_acked() -> None:
    message = AsyncMock()
    message.headers = None
    message.data = b"payload"
    consumer, subscription, handler = make_consumer(
        fetch_side_effect=[TimeoutError(), [message], asyncio.CancelledError()],
    )

    with pytest.raises(asyncio.CancelledError):
        await consumer._consume()

    assert subscription.fetch.await_count == 3
    handler.handle.assert_awaited_once_with(payload=b"payload", headers={})
    message.ack.assert_awaited_once_with()
    message.nak.assert_not_awaited()


async def test_broker_error_remains_visible_and_uses_existing_backoff(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    consumer, subscription, _ = make_consumer(
        fetch_side_effect=[ConnectionError("broker unavailable"), asyncio.CancelledError()],
    )
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)

    with caplog.at_level(logging.ERROR), pytest.raises(asyncio.CancelledError):
        await consumer._consume()

    assert subscription.fetch.await_count == 2
    sleep.assert_awaited_once_with(1)
    assert "Failed to fetch NATS messages" in caplog.text
