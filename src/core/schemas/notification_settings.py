from uuid import UUID

from pydantic import BaseModel, StrictBool


class NotificationSettingWrite(BaseModel):
    enabled: StrictBool


class NotificationSettingResponse(BaseModel):
    user_id: UUID
    event_code: str
    event_name: str
    event_description: str | None
    channel_code: str
    channel_name: str
    enabled: bool
