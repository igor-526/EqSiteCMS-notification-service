import abc
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class BaseSeeder[Plan, Existing, Missing](abc.ABC):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self) -> None:
        plan = await self.prepare()
        existing = await self.fetch_existing(plan)
        missing = self.diff(plan, existing)
        if missing:
            created = await self.create_missing(missing, plan, existing)
            logger.info("%s created %d entities", self.__class__.__name__, created)
            return
        logger.info("%s created 0 entities", self.__class__.__name__)

    @abc.abstractmethod
    async def prepare(self) -> Plan: ...

    @abc.abstractmethod
    async def fetch_existing(self, plan: Plan) -> Existing: ...

    @abc.abstractmethod
    def diff(self, plan: Plan, existing: Existing) -> Missing: ...

    @abc.abstractmethod
    async def create_missing(self, missing: Missing, plan: Plan, existing: Existing) -> int: ...
