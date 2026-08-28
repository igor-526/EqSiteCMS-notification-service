import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

from utils.seeding.init_registry import apply_migration

SERVICE_ROOT = Path(__file__).parents[2]


async def test_apply_migration_requests_disabled_logger_configuration() -> None:
    """In-process накат миграций обязан просить alembic не трогать конфигурацию логирования."""
    logger = logging.getLogger("tests.migration.logging.probe")
    logger.info("создан до применения миграций")
    captured: dict[str, Any] = {}

    def fake_upgrade(config: Any, revision: str) -> None:
        captured["configure_logger"] = config.attributes.get("configure_logger")

    with patch("utils.seeding.init_registry.command.upgrade", side_effect=fake_upgrade):
        await apply_migration()

    assert captured["configure_logger"] is False
    assert logger.disabled is False


def test_migration_env_respects_configure_logger_attribute() -> None:
    """
    `logging.config.fileConfig` по умолчанию выставляет `disable_existing_loggers=True` и глушит
    все ранее созданные логгеры, включая логгеры uvicorn и прикладных модулей. Guard в `env.py` —
    единственное, что отделяет сервис от полной потери логов после старта.
    """
    source = (SERVICE_ROOT / "src/migration/env.py").read_text()

    assert 'config.attributes.get("configure_logger", True)' in source
    assert source.index("config.attributes.get") < source.index("fileConfig(config.config_file_name)")
