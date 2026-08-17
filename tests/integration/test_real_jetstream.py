import asyncio
import os
import uuid
from pathlib import Path

import asyncpg
import pytest
from nats.aio.client import Client as NATS
from nats.errors import TimeoutError
from nats.js.api import AckPolicy, ConsumerConfig, DeliverPolicy, StreamConfig

from clients.nats.client import NatsJetstreamClient
from clients.nats.publisher import NotificationCommandsSendEmailEventPublisher
from core.schemas.messaging import CallbackRequestedData, NotificationCommandSendEmailData
from settings import NatsSettings


@pytest.mark.infrastructure
async def test_real_jetstream_delivery_contract() -> None:
    """Exercise broker semantics which cannot be established by adapter mocks."""
    suffix = uuid.uuid4().hex[:12]
    stream = f"IT_{suffix.upper()}"
    subject = f"it.{suffix}.events"
    other_subject = f"it.{suffix}.other"
    durable = f"it-{suffix}"
    nc = NATS()
    await asyncio.wait_for(nc.connect("nats://127.0.0.1:4222"), timeout=5)
    js = nc.jetstream()

    try:
        await js.add_stream(
            config=StreamConfig(
                name=stream,
                subjects=[f"it.{suffix}.*"],
                duplicate_window=60,
            )
        )
        await js.add_consumer(
            stream=stream,
            config=ConsumerConfig(
                durable_name=durable,
                filter_subject=subject,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=0.25,
                max_deliver=2,
            ),
        )
        consumer = await js.consumer_info(stream, durable)
        assert consumer.config.durable_name == durable
        assert consumer.config.filter_subject == subject
        assert consumer.config.ack_policy == AckPolicy.EXPLICIT
        assert consumer.config.max_deliver == 2

        first_ack = await js.publish(subject, b'{"value":1}', headers={"Nats-Msg-Id": suffix})
        duplicate_ack = await js.publish(subject, b'{"value":1}', headers={"Nats-Msg-Id": suffix})
        assert first_ack.duplicate is not True
        assert duplicate_ack.duplicate is True
        await js.publish(other_subject, b"filtered")

        subscription = await js.pull_subscribe(subject, durable=durable, stream=stream)
        first = (await subscription.fetch(1, timeout=2))[0]
        assert first.metadata is not None
        assert first.metadata.num_delivered == 1
        await first.nak()

        redelivered = (await subscription.fetch(1, timeout=2))[0]
        assert redelivered.metadata is not None
        assert redelivered.metadata.num_delivered == 2
        await redelivered.nak()

        with pytest.raises(TimeoutError):
            await subscription.fetch(1, timeout=0.75)

        state = await js.stream_info(stream)
        assert state.state.messages == 2  # duplicate was suppressed, other subject retained
    finally:
        try:
            await js.delete_stream(stream)
        finally:
            await nc.close()


@pytest.mark.infrastructure
async def test_real_backend_notification_email_adapter_compatibility() -> None:
    """Cross both canonical adapter boundaries through a real broker."""
    suffix = uuid.uuid4().hex[:12]
    backend_durable = f"it-backend-{suffix}"
    email_durable = f"it-email-{suffix}"
    settings = NatsSettings(nats_servers_raw="nats://127.0.0.1:4222")
    nc = NATS()
    await asyncio.wait_for(nc.connect("nats://127.0.0.1:4222"), timeout=5)
    js = nc.jetstream()
    callback_subscription = None
    email_subscription = None

    try:
        await js.add_consumer(
            stream=settings.nats_stream_site_events,
            config=ConsumerConfig(
                durable_name=backend_durable,
                filter_subject=settings.nats_subject_callback_requested,
                deliver_policy=DeliverPolicy.NEW,
                ack_policy=AckPolicy.EXPLICIT,
            ),
        )
        callback_subscription = await js.pull_subscribe(
            settings.nats_subject_callback_requested,
            durable=backend_durable,
            stream=settings.nats_stream_site_events,
        )

        backend_dir = Path(__file__).parents[3] / "backend"
        environment = os.environ | {
            "NATS_SERVERS": "nats://127.0.0.1:4222",
            "PYTHONPATH": str(backend_dir / "src"),
        }
        script = """
import asyncio, uuid
from clients.nats.client import NatsJetstreamClient
from clients.nats.publisher import CallbackRequestEventPublisher
from core.schemas import CallbackRequestedData
from settings import NatsSettings
async def main():
    settings = NatsSettings()
    client = NatsJetstreamClient(settings)
    await client.connect()
    try:
        await CallbackRequestEventPublisher(client=client, settings=settings).publish(
            payload=CallbackRequestedData(callback_request_id=uuid.uuid4(), phone='+70000000000'),
            equestrian_id=uuid.uuid4(),
        )
    finally:
        await client.close()
asyncio.run(main())
"""
        process = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "python",
            "-c",
            script,
            cwd=backend_dir,
            env=environment,
        )
        assert await asyncio.wait_for(process.wait(), timeout=15) == 0

        callback_message = (await callback_subscription.fetch(1, timeout=5))[0]
        callback = CallbackRequestedData.model_validate_json(callback_message.data)
        assert callback.phone == "+70000000000"
        assert callback_message.headers is not None
        assert uuid.UUID(callback_message.headers["X-Equestrian-Id"])
        assert uuid.UUID(callback_message.headers["Nats-Msg-Id"])
        await callback_message.ack()

        await js.add_consumer(
            stream=settings.nats_stream_notification_commands,
            config=ConsumerConfig(
                durable_name=email_durable,
                filter_subject=settings.nats_subject_notification_commands_send_email,
                deliver_policy=DeliverPolicy.NEW,
                ack_policy=AckPolicy.EXPLICIT,
            ),
        )
        email_subscription = await js.pull_subscribe(
            settings.nats_subject_notification_commands_send_email,
            durable=email_durable,
            stream=settings.nats_stream_notification_commands,
        )
        notification_client = NatsJetstreamClient(settings)
        await notification_client.connect()
        try:
            payload = NotificationCommandSendEmailData(
                event_uuid=uuid.uuid4(),
                to=["integration@example.test"],
                subject="real compatibility",
                body="test",
            )
            await NotificationCommandsSendEmailEventPublisher(
                client=notification_client,
                settings=settings,
            ).publish(payload=payload)
        finally:
            await notification_client.close()

        email_message = (await email_subscription.fetch(1, timeout=5))[0]
        decoded = NotificationCommandSendEmailData.model_validate_json(email_message.data)
        assert decoded == payload
        assert email_message.headers is not None
        assert uuid.UUID(email_message.headers["Nats-Msg-Id"])
        await email_message.ack()

        database = await asyncpg.connect(os.environ["EMAIL_TEST_DATABASE_DSN"])
        try:
            deadline = asyncio.get_running_loop().time() + 10
            while True:
                stored_id = await database.fetchval(
                    "SELECT id FROM email_logs WHERE event_uuid = $1",
                    payload.event_uuid,
                )
                if stored_id is not None:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise AssertionError("email-service did not persist the real NATS command")
                await asyncio.sleep(0.1)
            await database.execute("DELETE FROM email_logs WHERE event_uuid = $1", payload.event_uuid)
        finally:
            await database.close()
    finally:
        for durable, stream in (
            (backend_durable, settings.nats_stream_site_events),
            (email_durable, settings.nats_stream_notification_commands),
        ):
            try:
                await js.delete_consumer(stream, durable)
            except Exception:
                pass
        await nc.close()
