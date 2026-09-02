import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User


class AuthUserNotFoundError(ValueError):
    """Raised when a token is requested for an unknown user."""


class AuthInvalidCredentialsError(ValueError):
    """Raised when email/password combination is wrong."""


class AuthEmailAlreadyExistsError(ValueError):
    """Raised when registration email is already taken."""


@dataclass(frozen=True, slots=True)
class AccessToken:
    value: str
    expires_in: int


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_demo_token(self, user_id: uuid.UUID) -> AccessToken:
        """Issue a token for an existing user (demo-mode only)."""
        if await self._session.get(User, user_id) is None:
            raise AuthUserNotFoundError("User not found")

        token, expires_in = create_access_token(user_id)
        return AccessToken(value=token, expires_in=expires_in)

    async def register(self, email: str, password: str) -> AccessToken:
        """Create a new user with a hashed password and return a token."""
        user = User(
            email=email.strip().lower(),
            hashed_password=hash_password(password),
        )
        self._session.add(user)
        try:
            await self._session.commit()
            await self._session.refresh(user)
        except IntegrityError:
            await self._session.rollback()
            raise AuthEmailAlreadyExistsError(
                "A user with this email already exists"
            ) from None
        except Exception:
            await self._session.rollback()
            raise

        token, expires_in = create_access_token(user.id)
        return AccessToken(value=token, expires_in=expires_in)

    async def login(self, email: str, password: str) -> AccessToken:
        """Verify credentials and return a token."""
        result = await self._session.execute(
            select(User).where(User.email == email.strip().lower())
        )
        user = result.scalar_one_or_none()

        # Constant-time guard: always verify even if user doesn't exist
        # to prevent timing-based email enumeration.
        stored_hash = user.hashed_password if user else "$2b$12$" + "x" * 53
        valid = user is not None and verify_password(password, stored_hash or "")

        if not valid:
            raise AuthInvalidCredentialsError("Invalid email or password")

        token, expires_in = create_access_token(user.id)  # type: ignore[union-attr]
        return AccessToken(value=token, expires_in=expires_in)
