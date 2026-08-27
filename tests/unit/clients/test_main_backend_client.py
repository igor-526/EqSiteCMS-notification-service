from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clients.main_backend import MainBackendClient, MainBackendResponseError


def _session(monkeypatch, *, status: int = 200) -> MagicMock:
    response = AsyncMock()
    response.status = status
    response.text.return_value = "failure"
    response_context = MagicMock()
    response_context.__aenter__.return_value = response
    session = MagicMock()
    session.patch.return_value = response_context
    session_context = MagicMock()
    session_context.__aenter__.return_value = session
    monkeypatch.setattr(
        "clients.main_backend.client.aiohttp.ClientSession",
        MagicMock(return_value=session_context),
    )
    return session


@pytest.mark.asyncio
async def test_confirm_callback_delivery_uses_service_key_and_true_only(monkeypatch) -> None:
    session = _session(monkeypatch)
    callback_request_id = uuid4()
    client = MainBackendClient(base_url="http://backend:8000/", service_key="service-secret")

    await client.confirm_callback_delivery(callback_request_id=callback_request_id)

    session.patch.assert_called_once_with(
        f"http://backend:8000/api/service/callback_requests/{callback_request_id}/notifications-delivered",
        json={"notifications_delivered": True},
        headers={"X-Service-Key": "service-secret", "Content-Type": "application/json"},
    )


@pytest.mark.asyncio
async def test_confirm_callback_delivery_rejects_backend_error(monkeypatch) -> None:
    _session(monkeypatch, status=500)
    client = MainBackendClient(base_url="http://backend:8000", service_key="service-secret")

    with pytest.raises(MainBackendResponseError):
        await client.confirm_callback_delivery(callback_request_id=uuid4())


@pytest.mark.asyncio
async def test_get_users_combines_tenant_roles_and_service_key(monkeypatch) -> None:
    response = AsyncMock()
    response.status = 200
    response.json.return_value = {"items": [], "total": 0}
    response_context = MagicMock()
    response_context.__aenter__.return_value = response
    session = MagicMock()
    session.get.return_value = response_context
    session_context = MagicMock()
    session_context.__aenter__.return_value = session
    monkeypatch.setattr(
        "clients.main_backend.client.aiohttp.ClientSession",
        MagicMock(return_value=session_context),
    )
    tenant_id = uuid4()
    client = MainBackendClient(base_url="http://backend:8000", service_key="service-secret")

    result = await client.get_users(equestrian_ids=[tenant_id], role=["ADMIN", "SUPERUSER"])

    assert result.items == []
    session.get.assert_called_once_with(
        "http://backend:8000/api/service/users",
        params={
            "limit": 100,
            "offset": 0,
            "equestrian_ids": [str(tenant_id)],
            "role": ["ADMIN", "SUPERUSER"],
        },
        headers={"X-Service-Key": "service-secret", "Content-Type": "application/json"},
    )
