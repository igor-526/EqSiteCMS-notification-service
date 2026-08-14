"""HTTP-клиент для взаимодействия с email service."""

import logging
from uuid import UUID

import aiohttp
from pydantic import BaseModel, Field

from .exceptions import (
    EmailServiceConnectionError,
    EmailServiceResponseError,
    EmailServiceTimeoutError,
)

logger = logging.getLogger(__name__)


# === DTOs ===


class UserEmail(BaseModel):
    """DTO email пользователя из email service."""

    id: UUID
    user_id: UUID
    email: str
    approved: bool


# === Client ===


class EmailServiceClient:
    """HTTP-клиент для email service."""

    def __init__(self, base_url: str, service_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_key = service_key
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def get_user_emails(
        self,
        *,
        user_ids: list[UUID],
        approved: bool = True,
    ) -> list[UserEmail]:
        """
        Получить email'ы пользователей по списку user_ids.

        Args:
            user_ids: Список ID пользователей
            approved: Фильтр по статусу подтверждения

        Returns:
            Список UserEmail

        Raises:
            EmailServiceConnectionError: Ошибка соединения
            EmailServiceTimeoutError: Таймаут запроса
            EmailServiceResponseError: Ошибка ответа от сервера
        """
        url = f"{self._base_url}/emails"

        # Формируем query параметры
        params: dict = {
            "user_ids": ",".join(str(uid) for uid in user_ids),
        }
        if approved is not None:
            params["approved"] = str(approved).lower()

        headers = {
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status != 200:
                        text = await response.text()
                        raise EmailServiceResponseError(
                            status=response.status,
                            detail=f"Ошибка получения email'ов: {text}",
                        )

                    data = await response.json()
                    return [UserEmail.model_validate(item) for item in data]

        except aiohttp.ClientError as e:
            raise EmailServiceConnectionError(
                detail=f"Ошибка соединения с email service: {e!s}"
            ) from e
        except TimeoutError as e:
            raise EmailServiceTimeoutError(
                detail="Превышено время ожидания ответа от email service"
            ) from e
