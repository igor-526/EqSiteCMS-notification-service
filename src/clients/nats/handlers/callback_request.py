import logging
import uuid

from core.schemas.messaging import CallbackRequestedData
from core.services import CallbackRequestService

logger = logging.getLogger(__name__)


class CallbackRequestHandler:
    def __init__(
        self,
        *,
        service: CallbackRequestService,
    ) -> None:
        self._service = service

    async def handle(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> None:
        event_data = CallbackRequestedData.model_validate_json(
            payload,
        )
        try:
            equestrian_id = uuid.UUID(headers.get("X-Equestrian-Id"))
        except ValueError as ex:
            raise ValueError("Can't parse Equestrian UUID") from ex

        await self._service.process(
            payload=event_data,
            equestrian_id=equestrian_id,
        )
