from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from core.schemas import NotificationSettingResponse
from depends.notification_settings import get_notification_settings_service
from main import app


def response(*, user_id, enabled: bool) -> NotificationSettingResponse:
    return NotificationSettingResponse(
        user_id=user_id,
        event_code="callback",
        event_name="Callback",
        event_description=None,
        channel_code="email",
        channel_name="Email",
        enabled=enabled,
    )


def test_internal_read_is_owner_scoped_by_path() -> None:
    user_id = uuid4()
    service = AsyncMock()
    service.get_settings.return_value = [response(user_id=user_id, enabled=False)]
    app.dependency_overrides[get_notification_settings_service] = lambda: service
    try:
        result = TestClient(app).get(f"/internal/notification-settings/{user_id}")
    finally:
        app.dependency_overrides.clear()

    assert result.status_code == 200
    assert result.json()[0]["user_id"] == str(user_id)
    service.get_settings.assert_awaited_once_with(user_id=user_id)


def test_internal_write_passes_typed_idempotent_state() -> None:
    user_id = uuid4()
    service = AsyncMock()
    service.set_setting.return_value = response(user_id=user_id, enabled=True)
    app.dependency_overrides[get_notification_settings_service] = lambda: service
    try:
        result = TestClient(app).put(
            f"/internal/notification-settings/{user_id}/callback/email", json={"enabled": True}
        )
    finally:
        app.dependency_overrides.clear()

    assert result.status_code == 200
    service.set_setting.assert_awaited_once_with(
        user_id=user_id, event_code="callback", channel_code="email", enabled=True
    )


def test_internal_write_rejects_malformed_body_before_service() -> None:
    service = AsyncMock()
    app.dependency_overrides[get_notification_settings_service] = lambda: service
    try:
        result = TestClient(app).put(
            f"/internal/notification-settings/{uuid4()}/callback/email", json={"enabled": "yes"}
        )
    finally:
        app.dependency_overrides.clear()

    assert result.status_code == 400
    service.set_setting.assert_not_awaited()
