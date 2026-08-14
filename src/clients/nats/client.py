from nats import NATS
from nats.js import JetStreamContext
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy, PubAck, RetentionPolicy, StorageType, StreamConfig

from settings import NatsSettings


class NatsJetstreamClient:
    def __init__(self, settings: NatsSettings) -> None:
        self._settings = settings

        self._connection: NATS | None = None
        self._jetstream: JetStreamContext | None = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_connected

    def _get_jetstream(self) -> JetStreamContext:
        if self._jetstream is None or not self.is_connected:
            raise RuntimeError("NATS JetStream client is not connected")

        return self._jetstream

    @property
    def jetstream(self) -> JetStreamContext:
        return self._get_jetstream()

    async def connect(self) -> None:
        if self.is_connected:
            return

        self._connection = NATS()

        await self._connection.connect(
            servers=self._settings.nats_servers,
            name="notification-service",
            connect_timeout=5,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )

        self._jetstream = self._connection.jetstream()

    async def close(self) -> None:
        if self._connection is None:
            return

        try:
            if not self._connection.is_closed:
                await self._connection.drain()
        finally:
            self._connection = None
            self._jetstream = None

    async def setup(self) -> None:
        """
        Создаёт и актуализирует инфраструктуру JetStream,
        которой владеет основной backend.
        """
        if not self.is_connected:
            raise RuntimeError("NATS client must be connected before setup")

        await self.setup_streams()
        await self.setup_consumers()

    async def setup_streams(self) -> None:
        await self._setup_notification_commands_stream()

    async def setup_consumers(self) -> None:
        await self._setup_callback_requested_consumer()

    async def _setup_notification_commands_stream(self) -> None:
        jetstream = self._get_jetstream()

        config = StreamConfig(
            name=self._settings.nats_stream_notification_commands,
            subjects=self._settings.nats_subjects_notification_commands,
            storage=StorageType.FILE,
            retention=RetentionPolicy.LIMITS,
        )

        await jetstream.add_stream(config=config)

    async def _setup_callback_requested_consumer(self) -> None:
        jetstream = self._get_jetstream()

        await jetstream.add_consumer(
            stream=self._settings.nats_stream_site_events,
            config=ConsumerConfig(
                durable_name=(self._settings.nats_consumer_callback_requested),
                filter_subject=(self._settings.nats_subject_callback_requested),
                deliver_policy=DeliverPolicy.ALL,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=(self._settings.nats_consumer_ack_wait_seconds),
                max_deliver=(self._settings.nats_consumer_max_deliver),
            ),
        )

    async def publish(
        self,
        *,
        subject: str,
        payload: bytes,
        headers: dict[str, str] | None = None,
    ) -> PubAck:
        jetstream = self._get_jetstream()

        return await jetstream.publish(
            subject=subject,
            payload=payload,
            headers=headers,
        )
