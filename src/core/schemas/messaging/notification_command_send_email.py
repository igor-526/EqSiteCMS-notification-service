from pydantic import Field

from core.schemas.messaging.base_event_data import MessagingBaseEventData


class NotificationCommandSendEmailData(MessagingBaseEventData):
    email: str | None = Field(default=None, description="Email пользователя")
    text: str | None = Field(default=None, description="Комментарий заявителя")
