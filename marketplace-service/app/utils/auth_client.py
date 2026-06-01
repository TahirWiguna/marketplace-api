import httpx
from fastapi import HTTPException

from app.config import settings


class AuthClient:
    async def verify_token(self, token: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{settings.AUTH_SERVICE_URL}/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.RequestError:
            raise HTTPException(status_code=401, detail="Could not validate credentials")

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        return response.json()


auth_client = AuthClient()
