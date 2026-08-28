import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class PublishedCommand:
    """
    Результат публикации команды в JetStream.

    `duplicate` означает, что брокер уже принимал сообщение с этим `Nats-Msg-Id` в пределах
    `duplicate_window`: команда находится в stream и будет обработана consumer'ом, но текущая
    публикация нового сообщения не создала.
    """

    message_id: uuid.UUID
    duplicate: bool
