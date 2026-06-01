from fastapi import Header, HTTPException

from app.utils.auth_client import auth_client


async def get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    token = authorization.split(" ", 1)[1]
    return await auth_client.verify_token(token)
