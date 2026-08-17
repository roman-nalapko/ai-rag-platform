import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.user import User


class AuthUserNotFoundError(ValueError):
    """Raised when a token is requested for an unknown user."""


@dataclass(frozen=True, slots=True)
class AccessToken:
    value: str
    expires_in: int


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_demo_token(self, user_id: uuid.UUID) -> AccessToken:
        if await self._session.get(User, user_id) is None:
            raise AuthUserNotFoundError("User not found")

        token, expires_in = create_access_token(user_id)
        return AccessToken(value=token, expires_in=expires_in)
