from typing import Protocol
from uuid import UUID

from core.schemas.messaging import NotificationCommandSendEmailData, PublishedCommand


class NotificationCommandSendEmailPublisherProtocol(Protocol):
    async def publish(
        self,
        *,
        payload: NotificationCommandSendEmailData,
        idempotency_key: UUID | None = None,
    ) -> PublishedCommand: ...
