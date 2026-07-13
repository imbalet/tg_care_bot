from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort, UsernameSyncCache

ABSENT_USERNAME = "<absent>"
USERNAME_SYNC_TTL_SECONDS = 600


class UsernameSyncService:
    def __init__(
        self,
        *,
        backend: BackendPort,
        cache: UsernameSyncCache,
    ) -> None:
        self._backend = backend
        self._cache = cache

    async def sync(self, *, telegram_id: int, username: str | None) -> None:
        current = _normalize_value(username)
        cached = await self._cache.get(telegram_id)
        if cached == current:
            return
        try:
            await self._backend.update_customer_username(
                telegram_id=telegram_id,
                telegram_username=username,
            )
        except BackendClientError:
            return
        await self._cache.set(telegram_id, current, USERNAME_SYNC_TTL_SECONDS)


def _normalize_value(username: str | None) -> str:
    return username if username is not None else ABSENT_USERNAME
