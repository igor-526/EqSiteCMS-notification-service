"""Email service client."""

from .client import EmailServiceClient
from .exceptions import (
    EmailServiceClientError,
    EmailServiceConnectionError,
    EmailServiceResponseError,
    EmailServiceTimeoutError,
)

__all__ = [
    "EmailServiceClient",
    "EmailServiceClientError",
    "EmailServiceConnectionError",
    "EmailServiceResponseError",
    "EmailServiceTimeoutError",
]
