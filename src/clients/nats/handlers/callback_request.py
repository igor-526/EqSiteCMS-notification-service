import logging
import uuid

from core.schemas.messaging import CallbackRequestedData
from core.services import NotificationOrchestratorService

logger = logging.getLogger(__name__)


class CallbackRequestHandler:
    def __init__(
        self,
        *,
        orchestrator: NotificationOrchestratorService,
    ) -> None:
        self._orchestrator = orchestrator

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

        # Используем orchestrator для обработки через БД
        await self._orchestrator.process_event(
            event_code="callback",
            payload={
                "callback_request_id": str(event_data.callback_request_id),
                "name": event_data.name,
                "phone": event_data.phone,
                "comment": event_data.comment,
                "equestrian_id": str(equestrian_id),
            },
        )
