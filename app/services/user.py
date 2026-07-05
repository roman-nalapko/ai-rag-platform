from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserAlreadyExistsError(ValueError):
    """Raised when a user with the same email already exists."""


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, email: str) -> User:
        user = User(email=email.strip().lower())
        self._session.add(user)

        try:
            await self._session.commit()
            await self._session.refresh(user)
        except IntegrityError as error:
            await self._session.rollback()
            raise UserAlreadyExistsError(
                "A user with this email already exists"
            ) from error
        except Exception:
            await self._session.rollback()
            raise

        return user
