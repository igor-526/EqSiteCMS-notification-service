"""Клиенты для внешних сервисов."""

from .email_service import EmailServiceClient
from .main_backend import MainBackendClient

__all__ = ["EmailServiceClient", "MainBackendClient"]
