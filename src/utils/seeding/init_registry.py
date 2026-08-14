import asyncio
import logging
import os
from collections.abc import Callable

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession

from utils.database import SessionFactory
from utils.seeding.seeders import ChannelSeeder, EventSeeder
from utils.seeding.seeders.base_seeder import BaseSeeder

logger = logging.getLogger(__name__)

DEFAULT_MAX_ATTEMPTS = int(os.getenv("INIT_REGISTRY_MAX_ATTEMPTS", "5"))
DEFAULT_BACKOFF_SECONDS = float(os.getenv("INIT_REGISTRY_BACKOFF_SECONDS", "2"))


async def apply_migration(
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> None:
    for attempt in range(1, max_attempts + 1):
        alembic_config = Config("src/alembic.ini")
        alembic_config.set_main_option("script_location", "src/migration")
        alembic_config.attributes["configure_logger"] = False
        try:
            await asyncio.to_thread(command.upgrade, alembic_config, "head")
            logger.info("Миграции успешно были применены.")
            return
        except Exception as exc:
            if attempt >= max_attempts:
                logger.error(
                    "Не удалось применить миграции после %s попыток: %s",
                    max_attempts,
                    exc,
                )
                raise

            wait_time = backoff_seconds * attempt if backoff_seconds > 0 else 0
            logger.warning(
                "Ошибка наката миграций (попытка %s из %s): %s. Повтор через %.1f секунд.",
                attempt,
                max_attempts,
                exc,
                wait_time,
            )
            if wait_time:
                await asyncio.sleep(wait_time)


async def run_seeders_with_retry(
    factory: Callable[[AsyncSession], list[BaseSeeder]],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> None:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with SessionFactory() as session:
                logger.info("Starting seeding lifecycle...")
                seeders = factory(session)
                for seeder in seeders:
                    await seeder.run()
                await session.commit()
            logger.info("Сидирование завершено.")
            return
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts:
                logger.error("Сидирование не удалось после %s попыток: %s", max_attempts, exc)
                raise

            wait_time = backoff_seconds * attempt if backoff_seconds > 0 else 0
            logger.warning(
                "Ошибка сидирования (попытка %s из %s): %s. Повтор через %.1f секунд.",
                attempt,
                max_attempts,
                exc,
                wait_time,
            )
            if wait_time:
                await asyncio.sleep(wait_time)

    if last_error:
        raise last_error


def _build_seeders(session: AsyncSession) -> list[BaseSeeder]:
    return [ChannelSeeder(session), EventSeeder(session)]


async def init_registry() -> None:
    await apply_migration()
    await run_seeders_with_retry(_build_seeders)
