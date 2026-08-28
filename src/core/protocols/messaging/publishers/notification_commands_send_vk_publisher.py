from typing import Protocol
from uuid import UUID

from core.schemas.messaging import NotificationCommandSendVkData


class NotificationCommandSendVkPublisherProtocol(Protocol):
    async def publish(
        self,
        *,
        payload: NotificationCommandSendVkData,
        idempotency_key: UUID | None = None,
    ) -> UUID: ...
