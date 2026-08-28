import uuid

# Дедупликация JetStream действует на уровне stream, а не subject: два сообщения с одинаковым
# `Nats-Msg-Id` в пределах `duplicate_window` считаются дубликатами, даже если адресованы разным
# subjects одного stream. Поэтому идентификатор команды выводится из пары «корреляция + канал»,
# а не из одного `callback_request_id`.
NAMESPACE_NOTIFICATION_COMMAND = uuid.uuid5(uuid.NAMESPACE_DNS, "notification-commands.eqcms")


def build_command_msg_id(*, correlation_id: uuid.UUID, channel_code: str) -> uuid.UUID:
    """
    Детерминированный `Nats-Msg-Id` команды канала.

    Стабилен между повторными обработками одного и того же события, поэтому дедупликация
    продолжает защищать от двойной пользовательской отправки при redelivery, и одновременно
    различается между каналами одной корреляции.
    """
    return uuid.uuid5(NAMESPACE_NOTIFICATION_COMMAND, f"{correlation_id}:{channel_code}")
