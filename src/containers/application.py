from dependency_injector import containers, providers

from clients.email_service import EmailServiceClient
from clients.main_backend import MainBackendClient
from clients.nats import (
    CallbackRequestConsumer,
    CallbackRequestHandler,
    NatsJetstreamClient,
    NotificationCommandsSendEmailEventPublisher,
)
from core.services import (
    CallbackEventHandler,
    CallbackRequestService,
    EventHandlerRegistry,
    NotificationOrchestratorService,
)
from repositories import ChannelRepository, EventRepository, UserNotificationSettingRepository
from settings import (
    email_service_settings,
    main_backend_settings,
)
from settings import (
    nats_settings as nats_settings_instance,
)
from utils.database import SessionFactory


class ApplicationContainer(containers.DeclarativeContainer):
    nats_settings = providers.Object(nats_settings_instance)
    main_backend_settings = providers.Object(main_backend_settings)
    email_service_settings = providers.Object(email_service_settings)

    # NATS
    nats_client = providers.Singleton(
        NatsJetstreamClient,
        settings=nats_settings,
    )

    notification_commands_send_email_publisher = providers.Singleton(
        NotificationCommandsSendEmailEventPublisher,
        client=nats_client,
        settings=nats_settings,
    )

    # External clients
    main_backend_client = providers.Singleton(
        MainBackendClient,
        base_url=main_backend_settings.provided.main_backend_url,
        service_key=main_backend_settings.provided.main_backend_service_key,
    )

    email_service_client = providers.Singleton(
        EmailServiceClient,
        base_url=email_service_settings.provided.email_service_url,
    )

    # Repositories (per-session)
    session_factory = providers.Object(SessionFactory)

    channel_repository = providers.Factory(
        ChannelRepository,
        session=session_factory,
    )

    event_repository = providers.Factory(
        EventRepository,
        session=session_factory,
    )

    user_notification_setting_repository = providers.Factory(
        UserNotificationSettingRepository,
        session=session_factory,
    )

    # Event Handlers
    callback_event_handler = providers.Singleton(
        CallbackEventHandler,
        main_backend_client=main_backend_client,
        email_service_client=email_service_client,
    )

    event_handler_registry = providers.Singleton(
        EventHandlerRegistry,
    )

    # Services
    notification_orchestrator = providers.Singleton(
        NotificationOrchestratorService,
        channel_repository=channel_repository,
        event_repository=event_repository,
        user_setting_repository=user_notification_setting_repository,
        email_publisher=notification_commands_send_email_publisher,
        main_backend_client=main_backend_client,
        email_service_client=email_service_client,
    )

    callback_request_service = providers.Singleton(
        CallbackRequestService,
        email_publisher=notification_commands_send_email_publisher,
        main_backend_client=main_backend_client,
        email_service_client=email_service_client,
    )

    # NATS Handlers
    callback_request_handler = providers.Singleton(
        CallbackRequestHandler,
        service=callback_request_service,
        orchestrator=notification_orchestrator,
    )

    callback_request_consumer = providers.Singleton(
        CallbackRequestConsumer,
        client=nats_client,
        settings=nats_settings,
        handler=callback_request_handler,
    )
