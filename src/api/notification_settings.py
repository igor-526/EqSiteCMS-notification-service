from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from core.schemas import NotificationSettingResponse, NotificationSettingWrite
from core.services import NotificationSettingsService
from depends.notification_settings import get_notification_settings_service

router = APIRouter(prefix="/internal/notification-settings", tags=["Internal notification settings"])


@router.get("/{user_id}", response_model=list[NotificationSettingResponse])
async def get_notification_settings(
    user_id: UUID,
    service: Annotated[NotificationSettingsService, Depends(get_notification_settings_service)],
) -> list[NotificationSettingResponse]:
    return await service.get_settings(user_id=user_id)


@router.put("/{user_id}/{event_code}/{channel_code}", response_model=NotificationSettingResponse)
async def put_notification_setting(
    user_id: UUID,
    event_code: str,
    channel_code: str,
    payload: NotificationSettingWrite,
    service: Annotated[NotificationSettingsService, Depends(get_notification_settings_service)],
) -> NotificationSettingResponse:
    return await service.set_setting(
        user_id=user_id,
        event_code=event_code,
        channel_code=channel_code,
        enabled=payload.enabled,
    )
