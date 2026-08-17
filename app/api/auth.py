from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import DemoTokenRequest, TokenResponse
from app.services.auth import AuthService, AuthUserNotFoundError

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/demo-token", response_model=TokenResponse)
async def create_demo_token(
    request: DemoTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    try:
        token = await AuthService(session).create_demo_token(request.user_id)
    except AuthUserNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return TokenResponse(access_token=token.value, expires_in=token.expires_in)
