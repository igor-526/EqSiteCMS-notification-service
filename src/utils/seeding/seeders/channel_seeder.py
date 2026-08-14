from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.channel import ChannelEntity
from core.seeds.channels import CHANNEL_SEEDS
from models import notification_channels
from utils.seeding.seeders.simple_seeder import SimpleSeeder


class ChannelSeeder(SimpleSeeder[ChannelEntity]):
    """Seeds notification channels."""

    table = notification_channels
    entity_cls = ChannelEntity
    seeds = CHANNEL_SEEDS

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
