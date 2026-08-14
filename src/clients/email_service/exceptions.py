"""Exceptions for email service client."""

from core.exceptions.base import AppError


class EmailServiceClientError(AppError):
    """Базовая ошиб��а HTTP-клиента email service."""

    status_code = 500


class EmailServiceConnectionError(EmailServiceClientError):
    """Ошибка соединения с email service."""

    status_code = 500

    def __init__(self, detail: str = "Не удалось подключиться к email service") -> None:
        super().__init__(message=detail)


class EmailServiceTimeoutError(EmailServiceClientError):
    """Таймаут запроса к email service."""

    status_code = 500

    def __init__(self, detail: str = "Превышено время ожидания ответа от email service") -> None:
        super().__init__(message=detail)


class EmailServiceResponseError(EmailServiceClientError):
    """Ошибка ответа от email service."""

    status_code = 500

    def __init__(self, status: int, detail: str = "Ошибка при запросе к email service") -> None:
        self.status = status
        super().__init__(message=f"{detail} (HTTP {status})")
