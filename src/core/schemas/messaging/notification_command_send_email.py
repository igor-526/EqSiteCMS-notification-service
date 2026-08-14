from uuid import UUID

from pydantic import Field

from core.schemas.messaging.base_event_data import MessagingBaseEventData


class NotificationCommandSendEmailData(MessagingBaseEventData):
    """Схема команды на отправку email.

    Совместима с email-service NotificationCommandSendEmailData.
    """

    event_uuid: UUID = Field(..., description="Уникальный ID события для идемпотентности")
    to: list[str] = Field(..., min_length=1, description="Список получателей")
    subject: str = Field(..., min_length=1, max_length=500, description="Тема письма")
    body: str = Field(..., min_length=1, description="Тело письма (HTML)")
    cc: list[str] | None = Field(default=None, description="Копия")
    bcc: list[str] | None = Field(default=None, description="Скрытая копия")
    reply_to: str | None = Field(default=None, description="Адрес для ответа")
    from_name: str | None = Field(default=None, description="Имя отправителя")
    from_email: str | None = Field(default=None, description="Email отправителя")
