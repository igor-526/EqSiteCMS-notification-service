import json
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from clients.email_service.client import UserEmail
from clients.main_backend.client import PaginatedUsers, UserOutDto
from clients.nats.handlers.callback_request import CallbackRequestHandler
from core.entities.channel import ChannelEntity
from core.entities.event import EventEntity
from core.schemas.messaging import NotificationCommandSendVkData
from core.services import CallbackEventHandler, NotificationOrchestratorService
from smoke_harness.config import HarnessConfig, HarnessConfigurationError, PublisherOutcome
from smoke_harness.publishers import ScriptedEmailPublisher, ScriptedVkPublisher
from smoke_harness.runner import HarnessExecutionError, run_harness


def _environment(
    *,
    callback_id: UUID | None = None,
    user_id: UUID | None = None,
    email_outcome: str = "ack",
    vk_outcome: str = "ack",
    fixture_plan: list[dict[str, object]] | None = None,
) -> dict[str, str]:
    callback_id = callback_id or uuid4()
    user_id = user_id or uuid4()
    fixture_plan = fixture_plan or [
        {
            "user_id": str(user_id),
            "alias": "admin-a",
            "role": "ADMIN",
            "channels": ["email", "vk"],
            "email": "synthetic@example.test",
        }
    ]
    return {
        "EQSITECMS_SMOKE_HARNESS": "1",
        "EQSITECMS_ENVIRONMENT": "local",
        "EQSITECMS_SMOKE_RUN_ID": str(uuid4()),
        "EQSITECMS_SMOKE_CALLBACK_ID": str(callback_id),
        "EQSITECMS_SMOKE_SYNTHETIC_USER_IDS": ",".join(str(item["user_id"]) for item in fixture_plan),
        "EQSITECMS_SMOKE_FIXTURE_PLAN_JSON": json.dumps(fixture_plan),
        "EQSITECMS_SMOKE_EMAIL_OUTCOME": email_outcome,
        "EQSITECMS_SMOKE_VK_OUTCOME": vk_outcome,
        "EQSITECMS_SMOKE_CALLBACK_EVENT_JSON": json.dumps(
            {
                "occurred_at": datetime.now(UTC).isoformat(),
                "equestrian_id": str(uuid4()),
                "callback_request_id": str(callback_id),
                "name": "Synthetic",
                "phone": "+70000000000",
                "comment": "Harness",
            }
        ),
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("EQSITECMS_SMOKE_HARNESS", "0"),
        ("EQSITECMS_ENVIRONMENT", "production"),
        ("EQSITECMS_SMOKE_RUN_ID", "*"),
        ("EQSITECMS_SMOKE_SYNTHETIC_USER_IDS", ""),
        ("EQSITECMS_SMOKE_FIXTURE_PLAN_JSON", ""),
        ("EQSITECMS_SMOKE_FIXTURE_PLAN_JSON", '[{"user_id":"00000000-0000-0000-0000-000000000001"}]'),
    ],
)
def test_ht_nt_01_guard_rejects_before_dependency_factory(field: str, value: str) -> None:
    environment = _environment()
    environment[field] = value

    with pytest.raises(HarnessConfigurationError):
        HarnessConfig.from_environment(environment)


@dataclass
class _Dependencies:
    handler: CallbackRequestHandler
    close: AsyncMock


def _dependency_factory(*, confirmed: AsyncMock):
    event = EventEntity(
        id=uuid4(),
        code="callback",
        name="Callback",
        metadata={},
        is_active=True,
    )
    email_channel = ChannelEntity(id=uuid4(), code="email", name="Email", is_active=True)
    vk_channel = ChannelEntity(id=uuid4(), code="vk", name="VK", is_active=True)

    async def factory(
        config: HarnessConfig,
        email_publisher: ScriptedEmailPublisher,
        vk_publisher: ScriptedVkPublisher,
    ) -> _Dependencies:
        tenant_id = UUID(str(json.loads(config.callback_event_json)["equestrian_id"]))
        event_repository = AsyncMock()
        event_repository.get_by_code.return_value = event
        channel_repository = AsyncMock()
        channel_repository.get_active_channels.return_value = [email_channel, vk_channel]
        setting_repository = AsyncMock()
        channels = {"email": email_channel.id, "vk": vk_channel.id}
        setting_repository.get_users_by_event.return_value = [
            SimpleNamespace(user_id=fixture.user_id, channel_id=channels[channel])
            for fixture in config.recipients
            for channel in fixture.channels
        ]
        backend_client = AsyncMock()
        backend_client.get_users.return_value = PaginatedUsers(
            items=[
                UserOutDto(
                    id=fixture.user_id,
                    equestrian_id=tenant_id,
                    username=fixture.alias,
                    created_at="2026-08-27T00:00:00Z",
                )
                for fixture in config.recipients
                if fixture.role in {"ADMIN", "SUPERUSER"}
            ],
            total=sum(fixture.role in {"ADMIN", "SUPERUSER"} for fixture in config.recipients),
        )
        backend_client.confirm_callback_delivery = confirmed
        email_client = AsyncMock()
        email_client.get_user_emails.return_value = [
            UserEmail(id=uuid4(), user_id=fixture.user_id, email=fixture.email, approved=True)
            for fixture in config.recipients
            if fixture.email is not None and "email" in fixture.channels
        ]
        orchestrator = NotificationOrchestratorService(
            channel_repository=channel_repository,
            event_repository=event_repository,
            user_setting_repository=setting_repository,
            email_publisher=email_publisher,
            vk_publisher=vk_publisher,
            main_backend_client=backend_client,
            email_service_client=email_client,
        )
        orchestrator.register_handler(
            "callback",
            CallbackEventHandler(main_backend_client=backend_client, email_service_client=email_client),
        )
        handler = CallbackRequestHandler(orchestrator=orchestrator)
        return _Dependencies(handler=handler, close=AsyncMock())

    return factory


@pytest.mark.asyncio
async def test_ht_nt_02_scripted_composition_never_uses_nats_publishers() -> None:
    config = HarnessConfig.from_environment(_environment())
    confirmed = AsyncMock()
    cleanup = AsyncMock()

    result = await run_harness(
        config=config,
        dependency_factory=_dependency_factory(confirmed=confirmed),
        cleanup=cleanup,
    )

    assert result.email.attempts == 1
    assert result.vk.attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email_outcome", "vk_outcome", "expected_confirmation"),
    [("ack", "ack", 1), ("ack", "fail", 1), ("fail", "ack", 1)],
)
async def test_ht_nt_03_any_ack_confirms_once(
    email_outcome: str,
    vk_outcome: str,
    expected_confirmation: int,
) -> None:
    config = HarnessConfig.from_environment(_environment(email_outcome=email_outcome, vk_outcome=vk_outcome))
    confirmed = AsyncMock()

    expectation = pytest.raises(RuntimeError) if "fail" in (email_outcome, vk_outcome) else nullcontext()
    with expectation:
        await run_harness(
            config=config,
            dependency_factory=_dependency_factory(confirmed=confirmed),
            cleanup=AsyncMock(),
        )

    assert confirmed.await_count == expected_confirmation


@pytest.mark.asyncio
async def test_ht_nt_04_both_fail_without_confirmation() -> None:
    config = HarnessConfig.from_environment(_environment(email_outcome="fail", vk_outcome="fail"))
    confirmed = AsyncMock()

    with pytest.raises(HarnessExecutionError) as failure:
        await run_harness(
            config=config,
            dependency_factory=_dependency_factory(confirmed=confirmed),
            cleanup=AsyncMock(),
        )

    confirmed.assert_not_awaited()
    assert failure.value.result.completed is False
    assert failure.value.result.email.attempts == 1
    assert failure.value.result.email.outcome == "fail"
    assert failure.value.result.vk.attempts == 1
    assert failure.value.result.vk.outcome == "fail"


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["ack", "fail"])
async def test_ht_nt_05_cleanup_and_close_always_run_without_sensitive_output(
    outcome: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = HarnessConfig.from_environment(_environment(email_outcome=outcome, vk_outcome=outcome))
    confirmed = AsyncMock()
    cleanup = AsyncMock()
    dependencies: list[_Dependencies] = []
    factory = _dependency_factory(confirmed=confirmed)

    async def capturing_factory(*args):
        dependency = await factory(*args)
        dependencies.append(dependency)
        return dependency

    try:
        await run_harness(config=config, dependency_factory=capturing_factory, cleanup=cleanup)
    except RuntimeError:
        pass

    cleanup.assert_awaited_once_with(config)
    dependencies[0].close.assert_awaited_once()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.asyncio
async def test_ht_nt_05_factory_failure_still_runs_exact_cleanup() -> None:
    config = HarnessConfig.from_environment(_environment())
    unrelated_id = uuid4()
    state = {config.callback_request_id, unrelated_id}

    async def failing_factory(*args):
        del args
        raise RuntimeError("partial composition")

    async def exact_cleanup(cleanup_config: HarnessConfig) -> None:
        state.discard(cleanup_config.callback_request_id)

    with pytest.raises(RuntimeError, match="partial composition"):
        await run_harness(config=config, dependency_factory=failing_factory, cleanup=exact_cleanup)

    assert config.callback_request_id not in state
    assert unrelated_id in state


@pytest.mark.asyncio
async def test_ht_nt_05_partial_production_composition_closes_owned_session(monkeypatch: pytest.MonkeyPatch) -> None:
    import smoke_harness.composition as composition

    config = HarnessConfig.from_environment(_environment())
    session = AsyncMock()
    close_database = AsyncMock()
    monkeypatch.setattr(composition, "SessionFactory", lambda: session)
    monkeypatch.setattr(composition, "close_database", close_database)
    monkeypatch.setattr(composition, "NotificationOrchestratorService", MagicMock(side_effect=RuntimeError("wiring")))
    email_publisher = ScriptedEmailPublisher(
        callback_request_id=config.callback_request_id,
        expected_recipients=config.expected_email_recipients,
        outcome=PublisherOutcome.ACK,
    )
    vk_publisher = ScriptedVkPublisher(
        callback_request_id=config.callback_request_id,
        expected_recipients=config.expected_vk_recipients,
        outcome=PublisherOutcome.ACK,
    )

    with pytest.raises(RuntimeError, match="wiring"):
        await composition.build_production_dependencies(config, email_publisher, vk_publisher)

    session.close.assert_awaited_once()
    close_database.assert_awaited_once()


@pytest.mark.asyncio
async def test_ht_nt_evidence_reports_superuser_alias_without_identifiers() -> None:
    user_id = uuid4()
    config = HarnessConfig.from_environment(
        _environment(
            user_id=user_id,
            fixture_plan=[
                {
                    "user_id": str(user_id),
                    "alias": "super-a",
                    "role": "SUPERUSER",
                    "channels": ["email", "vk"],
                    "email": "synthetic@example.test",
                }
            ],
        )
    )

    result = await run_harness(
        config=config,
        dependency_factory=_dependency_factory(confirmed=AsyncMock()),
        cleanup=AsyncMock(),
    )

    evidence = repr(result)
    assert result.superuser_aliases == ("super-a",)
    assert result.email.recipient_aliases == ("super-a",)
    assert result.vk.recipient_aliases == ("super-a",)
    assert result.vk.contract_valid is True
    assert result.vk.text_fields_present is True
    assert result.vk.text_has_internal_uuid is False
    assert str(user_id) not in evidence
    assert "synthetic@example.test" not in evidence
    assert "+70000000000" not in evidence


@pytest.mark.asyncio
async def test_ht_nt_evidence_requires_exact_two_unique_vk_targets() -> None:
    first_id = uuid4()
    second_id = uuid4()
    config = HarnessConfig.from_environment(
        _environment(
            fixture_plan=[
                {"user_id": str(first_id), "alias": "admin-a", "role": "ADMIN", "channels": ["vk"]},
                {"user_id": str(second_id), "alias": "admin-b", "role": "ADMIN", "channels": ["vk"]},
            ]
        )
    )
    publisher = ScriptedVkPublisher(
        callback_request_id=config.callback_request_id,
        expected_recipients=config.expected_vk_recipients,
        outcome=PublisherOutcome.ACK,
    )

    payload = NotificationCommandSendVkData(
        occurred_at=datetime.now(UTC),
        event_uuid=uuid4(),
        callback_request_id=config.callback_request_id,
        user_ids=[first_id, second_id],
        text="Имя: Не указано\nТелефон: Не указан\nКомментарий: Без комментария",
    )
    await publisher.publish(payload=payload, idempotency_key=config.callback_request_id)

    evidence = publisher.evidence()
    assert evidence.recipient_aliases == ("admin-a", "admin-b")
    assert evidence.recipient_count == 2
    assert evidence.text_uses_fallback is True
    assert evidence.text_has_internal_uuid is False

    with pytest.raises(RuntimeError, match="exactly match"):
        await publisher.publish(
            payload=payload.model_copy(update={"user_ids": [first_id]}),
            idempotency_key=config.callback_request_id,
        )


@pytest.mark.asyncio
async def test_ht_nt_evidence_no_eligible_recipient_has_zero_channel_attempts() -> None:
    user_id = uuid4()
    config = HarnessConfig.from_environment(
        _environment(
            user_id=user_id,
            fixture_plan=[
                {
                    "user_id": str(user_id),
                    "alias": "visitor-a",
                    "role": "NON_ADMIN",
                    "channels": [],
                }
            ],
        )
    )

    result = await run_harness(
        config=config,
        dependency_factory=_dependency_factory(confirmed=AsyncMock()),
        cleanup=AsyncMock(),
    )

    assert result.email.attempts == 0
    assert result.email.recipient_aliases == ()
    assert result.vk.attempts == 0
    assert result.vk.recipient_aliases == ()
