"""
Auth dependency — validates our own HS256 JWT or falls back to dev mode.
Dev mode is active when SECRET_KEY is the default value ('change-me-in-production').
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import get_settings

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

_DEV_SECRET = "change-me-in-production"


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if not credentials:
        # Dev mode: secret key not changed → skip auth
        if settings.secret_key == _DEV_SECRET:
            return "dev-user"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str | None:
    """Returns user_id if authenticated, None otherwise. Never raises 401."""
    if not credentials:
        if settings.secret_key == _DEV_SECRET:
            return "dev-user"
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("sub") or None
    except JWTError:
        return None

