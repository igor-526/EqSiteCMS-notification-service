"""Протокол клиента main backend для использования в core слое."""

from typing import Any, Protocol
from uuid import UUID


class MainBackendClientProtocol(Protocol):
    """Протокол для HTTP-клиента main backend сервиса."""

    async def get_users(
        self,
        *,
        equestrian_ids: list[Any] | None = None,
        equestrian_service_keys: list[str] | None = None,
        role: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Any:
        """Получить список пользователей с фильтрацией и пагинацией."""
        ...

    async def confirm_callback_delivery(self, *, callback_request_id: UUID) -> None:
        """Подтвердить успешную публикацию callback email-команды."""
        ...
