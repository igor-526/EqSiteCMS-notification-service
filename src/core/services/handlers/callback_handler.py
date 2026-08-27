import logging
import uuid
from html import escape

from core.entities.event import EventEntity
from core.protocols.clients import EmailServiceClientProtocol, MainBackendClientProtocol
from core.schemas.messaging import NotificationCommandSendEmailData

logger = logging.getLogger(__name__)

SENDER_NAME = "EqSiteCMS"
CALLBACK_ELIGIBLE_ROLES: tuple[str, ...] = ("ADMIN", "SUPERUSER")


class CallbackEventHandler:
    def __init__(
        self,
        *,
        main_backend_client: MainBackendClientProtocol,
        email_service_client: EmailServiceClientProtocol,
    ) -> None:
        self._main_backend_client = main_backend_client
        self._email_service_client = email_service_client

    async def format_notification(
        self,
        *,
        channel_code: str,
        payload: dict,
        event: EventEntity,
        enabled_user_ids: set[uuid.UUID],
    ) -> NotificationCommandSendEmailData | None:
        if channel_code != "email":
            logger.warning("Unsupported channel for callback: %s", channel_code)
            return None

        name = payload.get("name")
        phone = payload.get("phone")
        comment = payload.get("comment")
        try:
            equestrian_id = uuid.UUID(str(payload["equestrian_id"]))
        except KeyError, TypeError, ValueError:
            logger.exception("Invalid tenant identity; callback notification suppressed")
            return None

        recipient_emails = await self._get_recipient_emails(
            equestrian_id=equestrian_id,
            enabled_user_ids=enabled_user_ids,
        )
        if not recipient_emails:
            logger.warning("No admin emails found, skipping notification")
            return None

        event_uuid = uuid.uuid4()
        subject = "Новый запрос на обратный звонок"
        body = self._build_email_body(
            name=name,
            phone=phone,
            comment=comment,
        )

        return NotificationCommandSendEmailData(
            event_uuid=event_uuid,
            to=recipient_emails,
            subject=subject,
            body=body,
            from_name=SENDER_NAME,
            from_email=None,
        )

    async def _get_recipient_emails(
        self,
        *,
        equestrian_id: uuid.UUID,
        enabled_user_ids: set[uuid.UUID],
    ) -> list[str]:
        """Intersect current role eligibility, enabled settings and confirmed emails."""
        if not enabled_user_ids:
            return []
        try:
            eligible_users = await self._main_backend_client.get_users(
                equestrian_ids=[equestrian_id],
                role=list(CALLBACK_ELIGIBLE_ROLES),
            )
            eligible_ids = {user.id for user in eligible_users.items}
            recipient_ids = eligible_ids & enabled_user_ids
            if not recipient_ids:
                logger.info("No eligible users with enabled callback email setting")
                return []

            emails = await self._email_service_client.get_user_emails(
                user_ids=list(recipient_ids),
                approved=True,
            )
            return [email.email for email in emails if email.approved and email.user_id in recipient_ids]
        except Exception:
            logger.exception("Recipient lookup failed; callback notification suppressed")
            return []

    @staticmethod
    def _build_email_body(
        *,
        name: str | None,
        phone: str | None,
        comment: str | None,
    ) -> str:
        name_display = escape(name) if name else "Не указано"
        comment_display = escape(comment) if comment else "Без комментария"
        phone_display = escape(phone) if phone else "Не указан"

        return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
  <h2 style="color: #2c5aa0;">Новый запрос на обратный звонок</h2>
  <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Имя:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{name_display}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Телефон:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{phone_display}</td>
    </tr>
    <tr>
      <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">Комментарий:</td>
      <td style="padding: 8px; border-bottom: 1px solid #eee;">{comment_display}</td>
    </tr>
  </table>
</body>
</html>"""
