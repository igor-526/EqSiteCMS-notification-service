from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from clients.nats.handlers.callback_request import CallbackRequestHandler
from smoke_harness.config import HarnessConfig
from smoke_harness.publishers import ChannelEvidence, ScriptedEmailPublisher, ScriptedVkPublisher


class HarnessDependencies(Protocol):
    handler: CallbackRequestHandler

    async def close(self) -> None: ...


DependencyFactory = Callable[
    [HarnessConfig, ScriptedEmailPublisher, ScriptedVkPublisher],
    Awaitable[HarnessDependencies],
]
CleanupHook = Callable[[HarnessConfig], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class HarnessResult:
    email: ChannelEvidence
    vk: ChannelEvidence
    superuser_aliases: tuple[str, ...]
    completed: bool


class HarnessExecutionError(RuntimeError):
    def __init__(self, result: HarnessResult) -> None:
        self.result = result
        super().__init__("scripted notification processing failed")


async def run_harness(
    *,
    config: HarnessConfig,
    dependency_factory: DependencyFactory,
    cleanup: CleanupHook,
) -> HarnessResult:
    email_publisher = ScriptedEmailPublisher(
        callback_request_id=config.callback_request_id,
        expected_recipients=config.expected_email_recipients,
        outcome=config.email_outcome,
    )
    vk_publisher = ScriptedVkPublisher(
        callback_request_id=config.callback_request_id,
        expected_recipients=config.expected_vk_recipients,
        outcome=config.vk_outcome,
    )
    dependencies: HarnessDependencies | None = None
    processing_error: Exception | None = None
    try:
        dependencies = await dependency_factory(config, email_publisher, vk_publisher)
        try:
            await dependencies.handler.handle(payload=config.callback_event_json, headers={})
        except Exception as exc:
            processing_error = exc
    finally:
        try:
            await cleanup(config)
        finally:
            if dependencies is not None:
                await dependencies.close()
    email_evidence = email_publisher.evidence()
    vk_evidence = vk_publisher.evidence()
    captured_aliases = {*email_evidence.recipient_aliases, *vk_evidence.recipient_aliases}
    result = HarnessResult(
        email=email_evidence,
        vk=vk_evidence,
        superuser_aliases=tuple(
            sorted(
                fixture.alias
                for fixture in config.recipients
                if fixture.role == "SUPERUSER" and fixture.alias in captured_aliases
            )
        ),
        completed=processing_error is None,
    )
    if processing_error is not None:
        raise HarnessExecutionError(result) from processing_error
    return result
