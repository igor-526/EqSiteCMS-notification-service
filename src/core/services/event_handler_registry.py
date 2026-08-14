import logging
from typing import Protocol

from core.entities.event import EventEntity
from core.schemas.messaging import NotificationCommandSendEmailData

logger = logging.getLogger(__name__)


class EventHandlerProtocol(Protocol):
    async def format_notification(
        self,
        *,
        channel_code: str,
        payload: dict,
        event: EventEntity,
    ) -> NotificationCommandSendEmailData | None: ...


class EventHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, EventHandlerProtocol] = {}

    def register(self, event_code: str, handler: EventHandlerProtocol) -> None:
        self._handlers[event_code] = handler
        logger.info("Handler registered for event: event_code=%s", event_code)

    def get_handler(self, event_code: str) -> EventHandlerProtocol | None:
        return self._handlers.get(event_code)
