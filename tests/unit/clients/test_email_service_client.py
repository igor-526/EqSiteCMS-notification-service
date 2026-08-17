from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clients.email_service.client import EmailServiceClient
from settings import EmailServiceSettings


def test_email_settings_have_no_peer_credential(monkeypatch) -> None:
    monkeypatch.setenv("EMAIL_SERVICE_SERVICE_KEY", "obsolete-peer-secret")

    configured = EmailServiceSettings(email_service_url="http://email-service:8000")

    assert "email_service_service_key" not in type(configured).model_fields
    assert configured.email_service_url == "http://email-service:8000"


@pytest.mark.asyncio
async def test_private_email_request_sends_no_peer_credential(monkeypatch) -> None:
    response = AsyncMock()
    response.status = 200
    response.json.return_value = []

    response_context = MagicMock()
    response_context.__aenter__.return_value = response

    session = MagicMock()
    session.get.return_value = response_context
    session_context = MagicMock()
    session_context.__aenter__.return_value = session
    session_factory = MagicMock(return_value=session_context)
    monkeypatch.setattr("clients.email_service.client.aiohttp.ClientSession", session_factory)

    client = EmailServiceClient(base_url="http://email-service:8000")
    assert await client.get_user_emails(user_ids=[uuid4()]) == []

    headers = session.get.call_args.kwargs["headers"]
    assert headers == {"Content-Type": "application/json"}
    assert "X-Service-Key" not in headers
    assert "Authorization" not in headers
