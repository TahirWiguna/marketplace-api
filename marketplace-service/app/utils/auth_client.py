import asyncio

import httpx
from fastapi import HTTPException

from app.config import settings


class AuthClient:
    """Client for verifying tokens against the auth-service.

    Hardened with:
    - Exponential backoff retries (max 3) for transient failures
    - Separate connect/read timeouts (5s connect, 10s read)
    - Graceful handling when auth-service is down (503, not 500)
    - Proper network error handling (ConnectionError, Timeout)
    """

    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds; doubles each retry
    CONNECT_TIMEOUT = 5.0
    READ_TIMEOUT = 10.0

    def _get_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.CONNECT_TIMEOUT,
            read=self.READ_TIMEOUT,
            write=self.READ_TIMEOUT,
            pool=self.CONNECT_TIMEOUT,
        )

    async def verify_token(self, token: str) -> dict:
        last_exc: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self._get_timeout()) as client:
                    response = await client.get(
                        f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
                        headers={"Authorization": f"Bearer {token}"},
                    )

                # 401 from auth-service is definitive — don't retry
                if response.status_code == 401:
                    raise HTTPException(
                        status_code=401, detail="Invalid or expired token"
                    )

                # 5xx from auth-service is transient — retry
                if response.status_code >= 500:
                    if attempt < self.MAX_RETRIES:
                        await asyncio.sleep(self.BASE_DELAY * (2 ** attempt))
                        continue
                    raise HTTPException(
                        status_code=503,
                        detail="Auth service unavailable",
                    )

                # Any other non-200 is unexpected
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=401, detail="Could not validate credentials"
                    )

                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.BASE_DELAY * (2 ** attempt))
                    continue
                # All retries exhausted — service is down
                raise HTTPException(
                    status_code=503,
                    detail="Auth service unavailable",
                )
            except HTTPException:
                raise

        # Shouldn't reach here, but safety net
        raise HTTPException(status_code=503, detail="Auth service unavailable")


auth_client = AuthClient()
