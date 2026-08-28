from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from clients.email_service import EmailServiceClient
from clients.main_backend import MainBackendClient
from clients.nats.handlers.callback_request import CallbackRequestHandler
from core.services import CallbackEventHandler, NotificationOrchestratorService
from repositories import ChannelRepository, EventRepository, UserNotificationSettingRepository
from settings import email_service_settings, main_backend_settings
from smoke_harness.config import HarnessConfig
from smoke_harness.publishers import ScriptedEmailPublisher, ScriptedVkPublisher
from utils.database import SessionFactory, close_database


@dataclass(slots=True)
class ProductionHarnessDependencies:
    handler: CallbackRequestHandler
    session: AsyncSession

    async def close(self) -> None:
        try:
            await self.session.close()
        finally:
            await close_database()


async def build_production_dependencies(
    config: HarnessConfig,
    email_publisher: ScriptedEmailPublisher,
    vk_publisher: ScriptedVkPublisher,
) -> ProductionHarnessDependencies:
    del config
    main_backend_client = MainBackendClient(
        base_url=main_backend_settings.main_backend_url,
        service_key=main_backend_settings.main_backend_service_key,
    )
    email_service_client = EmailServiceClient(base_url=email_service_settings.email_service_url)
    session = SessionFactory()
    try:
        orchestrator = NotificationOrchestratorService(
            channel_repository=ChannelRepository(session=session),
            event_repository=EventRepository(session=session),
            user_setting_repository=UserNotificationSettingRepository(session=session),
            email_publisher=email_publisher,
            vk_publisher=vk_publisher,
            main_backend_client=main_backend_client,
            email_service_client=email_service_client,
        )
        orchestrator.register_handler(
            "callback",
            CallbackEventHandler(
                main_backend_client=main_backend_client,
                email_service_client=email_service_client,
            ),
        )
        return ProductionHarnessDependencies(
            handler=CallbackRequestHandler(orchestrator=orchestrator),
            session=session,
        )
    except BaseException:
        try:
            await session.close()
        finally:
            await close_database()
        raise
