from uuid import UUID

from core.entities.channel import ChannelEntity

CHANNEL_SEEDS: list[ChannelEntity] = [
    ChannelEntity(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        code="email",
        name="Электронная почта",
        description="Доставка уведомлений на электронную почту пользователя",
        is_active=True,
    ),
    ChannelEntity(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        code="vk",
        name="VK",
        description="Доставка уведомлений от бота в социальную сеть VK",
        is_active=True,
    ),
    ChannelEntity(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        code="sms",
        name="СМС",
        description="Доставка СМС сообщений на мобильный номер телефона",
        is_active=True,
    ),
]
