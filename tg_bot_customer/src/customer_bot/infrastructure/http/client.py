import httpx

from .errors import BackendUnauthorizedError, BackendUnavailableError


class BackendClient:
    def __init__(
        self,
        base_url: str,
        service_key: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Service-Key": service_key},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def ping(self) -> None:
        try:
            response = await self._client.get("/internal/ping")
        except httpx.HTTPError as exc:
            raise BackendUnavailableError("Backend is unavailable") from exc
        if response.status_code == 401:
            raise BackendUnauthorizedError("Backend rejected service key")
        if response.status_code >= 400:
            raise BackendUnavailableError("Backend ping failed")


__all__ = ["BackendClient"]
