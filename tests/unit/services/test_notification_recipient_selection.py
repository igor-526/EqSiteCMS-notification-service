import uuid
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from core.entities.event import EventEntity
from core.schemas.messaging import NotificationCommandSendEmailData
from core.services.handlers.callback_handler import CallbackEventHandler


def make_handler() -> tuple[CallbackEventHandler, AsyncMock, AsyncMock]:
    backend = AsyncMock()
    email = AsyncMock()
    return CallbackEventHandler(main_backend_client=backend, email_service_client=email), backend, email


def event() -> EventEntity:
    return EventEntity(code="callback", name="Callback", is_active=True)


def payload() -> dict[str, str]:
    return {
        "callback_request_id": str(uuid4()),
        "equestrian_id": str(uuid4()),
        "phone": "+70000000000",
    }


@pytest.mark.asyncio
async def test_enabled_and_current_role_ids_are_intersected() -> None:
    handler, backend, email = make_handler()
    enabled_eligible, eligible_disabled = uuid4(), uuid4()
    backend.get_users.return_value = MagicMock(items=[MagicMock(id=enabled_eligible), MagicMock(id=eligible_disabled)])
    email.get_user_emails.return_value = [
        MagicMock(user_id=enabled_eligible, email="enabled@example.com", approved=True)
    ]

    payload_data = payload()
    result = await handler.format_notification(
        channel_code="email",
        payload=payload_data,
        event=event(),
        enabled_user_ids={enabled_eligible, uuid4()},
    )

    assert isinstance(result, NotificationCommandSendEmailData)
    assert result.to == ["enabled@example.com"]
    assert set(email.get_user_emails.await_args.kwargs["user_ids"]) == {enabled_eligible}
    backend.get_users.assert_awaited_once_with(
        equestrian_ids=[uuid.UUID(payload_data["equestrian_id"])],
        role=["ADMIN", "SUPERUSER"],
    )


@pytest.mark.asyncio
async def test_unconfirmed_email_is_discarded() -> None:
    handler, backend, email = make_handler()
    user_id = uuid4()
    backend.get_users.return_value = MagicMock(items=[MagicMock(id=user_id)])
    email.get_user_emails.return_value = [MagicMock(user_id=user_id, email="pending@example.com", approved=False)]

    result = await handler.format_notification(
        channel_code="email", payload=payload(), event=event(), enabled_user_ids={user_id}
    )

    assert result is None


@pytest.mark.asyncio
async def test_downstream_failure_is_fail_closed() -> None:
    handler, backend, email = make_handler()
    backend.get_users.side_effect = TimeoutError

    result = await handler.format_notification(
        channel_code="email", payload=payload(), event=event(), enabled_user_ids={uuid4()}
    )

    assert result is None
    email.get_user_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_intersection_does_not_lookup_email() -> None:
    handler, backend, email = make_handler()
    backend.get_users.return_value = MagicMock(items=[MagicMock(id=uuid4())])

    result = await handler.format_notification(
        channel_code="email", payload=payload(), event=event(), enabled_user_ids={uuid4()}
    )

    assert result is None
    email.get_user_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_enabled_settings_does_not_perform_any_recipient_lookup() -> None:
    handler, backend, email = make_handler()

    result = await handler.format_notification(
        channel_code="email", payload=payload(), event=event(), enabled_user_ids=set()
    )

    assert result is None
    backend.get_users.assert_not_awaited()
    email.get_user_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_foreign_email_user_id_is_discarded() -> None:
    handler, backend, email = make_handler()
    eligible_id = uuid4()
    backend.get_users.return_value = MagicMock(items=[MagicMock(id=eligible_id)])
    email.get_user_emails.return_value = [MagicMock(user_id=uuid4(), email="foreign@example.com", approved=True)]

    result = await handler.format_notification(
        channel_code="email", payload=payload(), event=event(), enabled_user_ids={eligible_id}
    )

    assert result is None


@pytest.mark.asyncio
async def test_email_lookup_failure_is_fail_closed() -> None:
    handler, backend, email = make_handler()
    eligible_id = uuid4()
    backend.get_users.return_value = MagicMock(items=[MagicMock(id=eligible_id)])
    email.get_user_emails.side_effect = RuntimeError("email unavailable")

    result = await handler.format_notification(
        channel_code="email", payload=payload(), event=event(), enabled_user_ids={eligible_id}
    )

    assert result is None


@pytest.mark.asyncio
async def test_malformed_or_missing_tenant_is_fail_closed_without_lookups() -> None:
    for tenant_payload in (
        {"callback_request_id": str(uuid4()), "phone": "+70000000000"},
        {
            "callback_request_id": str(uuid4()),
            "equestrian_id": "malformed",
            "phone": "+70000000000",
        },
    ):
        handler, backend, email = make_handler()
        result = await handler.format_notification(
            channel_code="email",
            payload=tenant_payload,
            event=event(),
            enabled_user_ids={uuid4()},
        )
        assert result is None
        backend.get_users.assert_not_awaited()
        email.get_user_emails.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_channel_performs_no_lookups() -> None:
    handler, backend, email = make_handler()

    result = await handler.format_notification(
        channel_code="sms", payload=payload(), event=event(), enabled_user_ids={uuid4()}
    )

    assert result is None
    backend.get_users.assert_not_awaited()
    email.get_user_emails.assert_not_awaited()
