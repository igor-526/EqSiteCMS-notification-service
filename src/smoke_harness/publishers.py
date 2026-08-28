import re
from dataclasses import dataclass
from uuid import UUID, uuid4

from core.schemas.messaging import NotificationCommandSendEmailData, NotificationCommandSendVkData
from smoke_harness.config import PublisherOutcome, RecipientFixture


class ScriptedPublishError(RuntimeError):
    """Deterministic failure without downstream publication."""


@dataclass(frozen=True, slots=True)
class ChannelEvidence:
    attempts: int
    outcome: str
    recipient_aliases: tuple[str, ...]
    recipient_count: int
    contract_valid: bool
    text_fields_present: bool | None = None
    text_uses_fallback: bool | None = None
    text_has_internal_uuid: bool | None = None


class ScriptedEmailPublisher:
    def __init__(
        self,
        *,
        callback_request_id: UUID,
        expected_recipients: dict[str, RecipientFixture],
        outcome: PublisherOutcome,
    ) -> None:
        self._callback_request_id = callback_request_id
        self._expected_recipients = expected_recipients
        self._outcome = outcome
        self.attempts = 0
        self._recipient_aliases: tuple[str, ...] = ()

    async def publish(
        self,
        *,
        payload: NotificationCommandSendEmailData,
        idempotency_key: UUID | None = None,
    ) -> UUID:
        if idempotency_key != self._callback_request_id:
            raise ScriptedPublishError("publisher target is outside the synthetic callback")
        if set(payload.to) != set(self._expected_recipients):
            raise ScriptedPublishError("email recipients do not exactly match the fixture plan")
        self._recipient_aliases = tuple(sorted(self._expected_recipients[email].alias for email in payload.to))
        self.attempts += 1
        if self._outcome is PublisherOutcome.FAIL:
            raise ScriptedPublishError("scripted email publisher failure")
        return uuid4()

    def evidence(self) -> ChannelEvidence:
        return ChannelEvidence(
            attempts=self.attempts,
            outcome=self._outcome.value,
            recipient_aliases=self._recipient_aliases,
            recipient_count=len(self._recipient_aliases),
            contract_valid=self.attempts > 0,
        )


class ScriptedVkPublisher:
    def __init__(
        self,
        *,
        callback_request_id: UUID,
        expected_recipients: dict[UUID, RecipientFixture],
        outcome: PublisherOutcome,
    ) -> None:
        self._callback_request_id = callback_request_id
        self._expected_recipients = expected_recipients
        self._outcome = outcome
        self.attempts = 0
        self._recipient_aliases: tuple[str, ...] = ()
        self._contract_valid = False
        self._text_fields_present = False
        self._text_uses_fallback = False
        self._text_has_internal_uuid = False

    async def publish(
        self,
        *,
        payload: NotificationCommandSendVkData,
        idempotency_key: UUID | None = None,
    ) -> UUID:
        if idempotency_key != self._callback_request_id or payload.callback_request_id != self._callback_request_id:
            raise ScriptedPublishError("publisher target is outside the synthetic callback")
        if set(payload.user_ids) != set(self._expected_recipients):
            raise ScriptedPublishError("VK recipients do not exactly match the fixture plan")
        self._recipient_aliases = tuple(
            sorted(self._expected_recipients[user_id].alias for user_id in payload.user_ids)
        )
        self._contract_valid = NotificationCommandSendVkData.model_validate(payload.model_dump()) == payload
        self._text_fields_present = all(label in payload.text for label in ("Имя:", "Телефон:", "Комментарий:"))
        self._text_uses_fallback = any(
            fallback in payload.text for fallback in ("Не указано", "Не указан", "Без комментария")
        )
        internal_ids = {self._callback_request_id, *self._expected_recipients}
        self._text_has_internal_uuid = bool(re.search(r"[0-9a-fA-F-]{36}", payload.text)) or any(
            str(internal_id) in payload.text for internal_id in internal_ids
        )
        self.attempts += 1
        if self._outcome is PublisherOutcome.FAIL:
            raise ScriptedPublishError("scripted VK publisher failure")
        return uuid4()

    def evidence(self) -> ChannelEvidence:
        return ChannelEvidence(
            attempts=self.attempts,
            outcome=self._outcome.value,
            recipient_aliases=self._recipient_aliases,
            recipient_count=len(self._recipient_aliases),
            contract_valid=self._contract_valid,
            text_fields_present=self._text_fields_present,
            text_uses_fallback=self._text_uses_fallback,
            text_has_internal_uuid=self._text_has_internal_uuid,
        )
