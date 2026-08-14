import asyncio
import logging

from nats.aio.msg import Msg
from nats.errors import TimeoutError
from nats.js import JetStreamContext

from clients.nats.client import NatsJetstreamClient
from core.protocols.messaging.handlers.callback_request import (
    CallbackRequestHandlerProtocol,
)
from settings import NatsSettings

logger = logging.getLogger(__name__)


class CallbackRequestConsumer:
    def __init__(
        self,
        *,
        client: NatsJetstreamClient,
        settings: NatsSettings,
        handler: CallbackRequestHandlerProtocol,
    ) -> None:
        self._client = client
        self._settings = settings
        self._handler = handler

        self._task: asyncio.Task[None] | None = None
        self._subscription: JetStreamContext.PullSubscription | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            return

        self._subscription = await self._client.jetstream.pull_subscribe(
            subject=self._settings.nats_subject_callback_requested,
            durable=self._settings.nats_consumer_callback_requested,
            stream=self._settings.nats_stream_site_events,
        )

        self._task = asyncio.create_task(
            self._consume(),
            name="callback-request-consumer",
        )

    async def stop(self) -> None:
        if self._task is None:
            return

        self._task.cancel()

        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            self._subscription = None

    async def _consume(self) -> None:
        if self._subscription is None:
            logger.error("Consumer started without subscription")
            return

        while True:
            try:
                messages = await self._subscription.fetch(
                    batch=self._settings.nats_consumer_fetch_batch_size,
                    timeout=self._settings.nats_consumer_fetch_timeout_seconds,
                )
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to fetch NATS messages")
                await asyncio.sleep(1)
                continue

            for message in messages:
                await self._process_message(message)

    async def _process_message(self, message: Msg) -> None:
        headers = dict(message.headers) if message.headers is not None else {}

        try:
            await self._handler.handle(
                payload=message.data,
                headers=headers,
            )
        except Exception:
            logger.exception(
                "Failed to process NATS message",
            )
            await message.nak()
            return

        await message.ack()
