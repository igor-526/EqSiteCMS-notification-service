import logging
import uuid

from core.protocols.messaging import NotificationCommandSendEmailPublisherProtocol
from core.schemas.messaging import CallbackRequestedData, NotificationCommandSendEmailData

logger = logging.getLogger(__name__)


class CallbackRequestService:
    def __init__(
        self,
        *,
        email_publisher: NotificationCommandSendEmailPublisherProtocol,
    ) -> None:
        self._email_publisher = email_publisher

    async def process(
        self,
        *,
        payload: CallbackRequestedData,
        equestrian_id: uuid.UUID,
    ) -> None:
        print(payload)
        print(equestrian_id)

        email_payload = NotificationCommandSendEmailData(
            email="iigorrr526@gmail.com",
            text="Test email"
        )
        event_id = await self._email_publisher.publish(payload=email_payload)
        print({"status": "ok", "event_id": str(event_id)})
