from typing import Protocol
from uuid import UUID

from core.schemas.messaging import NotificationCommandSendEmailData


class NotificationCommandSendEmailPublisherProtocol(Protocol):
    async def publish(
        self,
        *,
        payload: NotificationCommandSendEmailData,
    ) -> UUID: ...
