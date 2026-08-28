import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import cast
from uuid import UUID


class HarnessConfigurationError(ValueError):
    """Raised before any external dependency is created."""


class PublisherOutcome(StrEnum):
    ACK = "ack"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class RecipientFixture:
    user_id: UUID
    alias: str
    role: str
    channels: frozenset[str]
    email: str | None = None


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    run_id: UUID
    callback_request_id: UUID
    synthetic_user_ids: tuple[UUID, ...]
    recipients: tuple[RecipientFixture, ...]
    callback_event_json: bytes
    email_outcome: PublisherOutcome
    vk_outcome: PublisherOutcome

    @classmethod
    def from_environment(cls, environment: dict[str, str]) -> HarnessConfig:
        if environment.get("EQSITECMS_SMOKE_HARNESS") != "1":
            raise HarnessConfigurationError("smoke harness is disabled")
        if environment.get("EQSITECMS_ENVIRONMENT", "").strip().lower() != "local":
            raise HarnessConfigurationError("smoke harness requires the local environment")

        run_id = _required_uuid(environment, "EQSITECMS_SMOKE_RUN_ID")
        callback_request_id = _required_uuid(environment, "EQSITECMS_SMOKE_CALLBACK_ID")
        user_ids = _required_uuid_list(environment, "EQSITECMS_SMOKE_SYNTHETIC_USER_IDS")
        recipients = _required_fixture_plan(environment, user_ids)
        event_json = environment.get("EQSITECMS_SMOKE_CALLBACK_EVENT_JSON", "").strip()
        if not event_json:
            raise HarnessConfigurationError("synthetic callback event is required")
        try:
            event = json.loads(event_json)
        except json.JSONDecodeError as exc:
            raise HarnessConfigurationError("synthetic callback event must be valid JSON") from exc
        if not isinstance(event, dict) or event.get("callback_request_id") != str(callback_request_id):
            raise HarnessConfigurationError("synthetic callback target does not match the event")

        try:
            email_outcome = PublisherOutcome(environment.get("EQSITECMS_SMOKE_EMAIL_OUTCOME", ""))
            vk_outcome = PublisherOutcome(environment.get("EQSITECMS_SMOKE_VK_OUTCOME", ""))
        except ValueError as exc:
            raise HarnessConfigurationError("publisher outcomes must be exact ack or fail values") from exc

        return cls(
            run_id=run_id,
            callback_request_id=callback_request_id,
            synthetic_user_ids=user_ids,
            recipients=recipients,
            callback_event_json=event_json.encode(),
            email_outcome=email_outcome,
            vk_outcome=vk_outcome,
        )

    @property
    def expected_vk_recipients(self) -> dict[UUID, RecipientFixture]:
        return {fixture.user_id: fixture for fixture in self.recipients if "vk" in fixture.channels}

    @property
    def expected_email_recipients(self) -> dict[str, RecipientFixture]:
        return {
            fixture.email: fixture
            for fixture in self.recipients
            if "email" in fixture.channels and fixture.email is not None
        }


def _required_uuid(environment: dict[str, str], name: str) -> UUID:
    raw = environment.get(name, "").strip()
    if not raw or any(marker in raw for marker in ("*", "?", ">")):
        raise HarnessConfigurationError(f"{name} must be an exact UUID")
    try:
        value = UUID(raw)
    except ValueError as exc:
        raise HarnessConfigurationError(f"{name} must be an exact UUID") from exc
    if value.int == 0:
        raise HarnessConfigurationError(f"{name} must not be nil")
    return value


def _required_uuid_list(environment: dict[str, str], name: str) -> tuple[UUID, ...]:
    raw_values = [item.strip() for item in environment.get(name, "").split(",") if item.strip()]
    if not raw_values:
        raise HarnessConfigurationError(f"{name} must contain exact synthetic targets")
    values = tuple(_required_uuid({name: raw}, name) for raw in raw_values)
    if len(values) != len(set(values)):
        raise HarnessConfigurationError(f"{name} must contain unique targets")
    return values


def _required_fixture_plan(
    environment: dict[str, str],
    synthetic_user_ids: tuple[UUID, ...],
) -> tuple[RecipientFixture, ...]:
    raw = environment.get("EQSITECMS_SMOKE_FIXTURE_PLAN_JSON", "").strip()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HarnessConfigurationError("fixture plan must be valid JSON") from exc
    if not isinstance(items, list) or not items:
        raise HarnessConfigurationError("fixture plan must contain exact synthetic recipients")
    fixtures: list[RecipientFixture] = []
    for item in items:
        if not isinstance(item, dict):
            raise HarnessConfigurationError("fixture plan entries must be objects")
        user_id = _required_uuid({"user_id": str(item.get("user_id", ""))}, "user_id")
        alias = str(item.get("alias", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", alias):
            raise HarnessConfigurationError("fixture aliases must be sanitized identifiers")
        role = str(item.get("role", ""))
        if role not in {"ADMIN", "SUPERUSER", "NON_ADMIN", "FOREIGN_ADMIN"}:
            raise HarnessConfigurationError("fixture role is not allowed")
        channels_raw = item.get("channels")
        invalid_channels = not isinstance(channels_raw, list)
        if isinstance(channels_raw, list):
            channel_types_valid = all(isinstance(channel, str) for channel in channels_raw)
            invalid_channels = not channel_types_valid
            if channel_types_valid:
                invalid_channels = not set(channels_raw) <= {"email", "vk"}
        if invalid_channels:
            raise HarnessConfigurationError("fixture channels must contain only email or vk")
        channels = tuple(cast(list[str], channels_raw))
        email = item.get("email")
        if "email" in channels and (not isinstance(email, str) or not email.endswith("@example.test")):
            raise HarnessConfigurationError("email fixtures must use the synthetic example.test domain")
        fixtures.append(
            RecipientFixture(
                user_id=user_id,
                alias=alias,
                role=role,
                channels=frozenset(channels),
                email=email if isinstance(email, str) else None,
            )
        )
    if {fixture.user_id for fixture in fixtures} != set(synthetic_user_ids):
        raise HarnessConfigurationError("fixture plan must exactly match synthetic targets")
    if len({fixture.alias for fixture in fixtures}) != len(fixtures):
        raise HarnessConfigurationError("fixture aliases must be unique")
    return tuple(fixtures)
