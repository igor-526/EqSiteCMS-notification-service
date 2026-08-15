"""Протокол клиента email service для использования в core слое."""

from typing import Any, Protocol


class EmailServiceClientProtocol(Protocol):
    """Протокол для HTTP-клиента email service."""

    async def get_user_emails(
        self,
        *,
        user_ids: list[Any],
        approved: bool = True,
    ) -> list[Any]:
        """Получить email'ы пользователей по списку user_ids."""
        ...
