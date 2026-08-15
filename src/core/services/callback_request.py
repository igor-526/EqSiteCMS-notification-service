import logging
import uuid

from core.protocols.clients import EmailServiceClientProtocol, MainBackendClientProtocol
from core.protocols.messaging import NotificationCommandSendEmailPublisherProtocol
from core.schemas.messaging import CallbackRequestedData, NotificationCommandSendEmailData

logger = logging.getLogger(__name__)

SENDER_NAME = "EqSiteCMS"
SENDER_EMAIL = None  # Используется default из SMTP настроек


class CallbackRequestService:
    def __init__(
        self,
        *,
        email_publisher: NotificationCommandSendEmailPublisherProtocol,
        main_backend_client: MainBackendClientProtocol,
        email_service_client: EmailServiceClientProtocol,
    ) -> None:
        self._email_publisher = email_publisher
        self._main_backend_client = main_backend_client
        self._email_service_client = email_service_client

    async def process(
        self,
        *,
        payload: CallbackRequestedData,
        equestrian_id: uuid.UUID,
    ) -> None:
        logger.info(
            "Processing callback request: callback_request_id=%s, equestrian_id=%s, name=%s, phone=%s",
            payload.callback_request_id,
            equestrian_id,
            payload.name,
            payload.phone,
        )

        # Получаем email адреса администраторов
        recipient_emails = await self._get_admin_emails()
        if not recipient_emails:
            logger.warning("No admin emails found, skipping notification")
            return

        event_uuid = uuid.uuid4()

        subject = "Новый запрос на обратный звонок"
        body = self._build_email_body(
            callback_request_id=payload.callback_request_id,
            name=payload.name,
            phone=payload.phone,
            comment=payload.comment,
            equestrian_id=equestrian_id,
        )

        email_payload = NotificationCommandSendEmailData(
            event_uuid=event_uuid,
            to=recipient_emails,
            subject=subject,
            body=body,
            from_name=SENDER_NAME,
            from_email=SENDER_EMAIL,
        )

        event_id = await self._email_publisher.publish(payload=email_payload)
        logger.info("Email event published: event_id=%s, event_uuid=%s", event_id, event_uuid)

    async def _get_admin_emails(self) -> list[str]:
        """Получить email адреса администраторов платформы."""
        try:
            # Получаем администраторов из main backend
            admins = await self._main_backend_client.get_users(role=["admin"])
            if not admins.items:
                logger.warning("No admin users found")
                return []

            # Получаем email адреса из email service
            user_ids = [admin.id for admin in admins.items]
            emails = await self._email_service_client.get_user_emails(
                user_ids=user_ids,
                approved=True,
            )

            return [email.email for email in emails]
        except Exception:
            logger.exception("Failed to get admin emails")
            return []

    @staticmethod
    def _build_email_body(
        *,
        callback_request_id: uuid.UUID,
        name: str | None,
        phone: str,
        comment: str | None,
        equestrian_id: uuid.UUID,
    ) -> str:
        """Формирует HTML тело письма с данными заявки."""
        name_display = name or "Не указано"
        comment_display = comment or "Без комментария"

        return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <h2 style="color: #2c5aa0;">Новый запрос на обратный звонок</h2>
  <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">ID заявки:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{callback_request_id}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Имя:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{name_display}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Телефон:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{phone}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Комментарий:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{comment_display}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">ID всадника:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{equestrian_id}</td>
    </tr>
  </table>
</body>
</html>"""
