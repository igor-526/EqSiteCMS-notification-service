from uuid import UUID

from core.entities.event import EventEntity

EVENT_SEEDS: list[EventEntity] = [
    EventEntity(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        code="callback",
        name="Обратный звонок",
        description="Обработка формы заявки на обратный звонок",
        metadata={
            "phone": {"required": True, "type": "phone_number"},
            "comment": {"required": False, "type": "string"},
            "equestrian_id": {"required": True, "type": "uuid4"},
        },
        is_active=True,
    ),
]
