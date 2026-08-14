from dependency_injector import containers, providers

from clients.nats import (
    CallbackRequestConsumer,
    CallbackRequestHandler,
    NatsJetstreamClient,
    NotificationCommandsSendEmailEventPublisher,
)
from core.services import CallbackRequestService
from settings import nats_settings as nats_settings_instance


class ApplicationContainer(containers.DeclarativeContainer):
    nats_settings = providers.Object(nats_settings_instance)

    nats_client = providers.Singleton(
        NatsJetstreamClient,
        settings=nats_settings,
    )

    notification_commands_send_email_publisher = providers.Singleton(
        NotificationCommandsSendEmailEventPublisher,
        client=nats_client,
        settings=nats_settings,
    )

    callback_request_service = providers.Singleton(
        CallbackRequestService,
        email_publisher=notification_commands_send_email_publisher
    )

    callback_request_handler = providers.Singleton(
        CallbackRequestHandler,
        service=callback_request_service,
    )

    callback_request_consumer = providers.Singleton(
        CallbackRequestConsumer,
        client=nats_client,
        settings=nats_settings,
        handler=callback_request_handler,
    )
