from typing import Protocol


class CallbackRequestHandlerProtocol(Protocol):
    async def handle(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> None: ...
