from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.event import EventEntity
from core.seeds.events import EVENT_SEEDS
from models import notification_events
from utils.seeding.seeders.simple_seeder import SimpleSeeder


class EventSeeder(SimpleSeeder[EventEntity]):
    """Seeds notification events."""

    table = notification_events
    entity_cls = EventEntity
    seeds = EVENT_SEEDS

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
