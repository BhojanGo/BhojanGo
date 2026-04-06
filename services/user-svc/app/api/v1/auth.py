from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import (
    AuthTokensResponse,
    LoginRequest,
    MessageResponse,
    OtpSendRequest,
    OtpVerifyRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SocialLoginRequest,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = structlog.get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)
security = HTTPBearer()


@router.post("/register", response_model=AuthTokensResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokensResponse:
    """Register a new customer account."""
    return await AuthService(db).register(data)


@router.post("/login", response_model=AuthTokensResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokensResponse:
    """Login with email and password."""
    return await AuthService(db).login(data)


@router.post("/refresh", response_model=AuthTokensResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokensResponse:
    """Exchange a refresh token for a new access + refresh token pair."""
    return await AuthService(db).refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Logout — invalidates the current access token and all refresh tokens."""
    await AuthService(db).logout(credentials.credentials, str(current_user.id))
    return MessageResponse(message="Logged out successfully")


@router.post("/send-otp", response_model=MessageResponse)
@limiter.limit("3/minute")
async def send_otp(
    request: Request,
    data: OtpSendRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Send a 6-digit OTP to the given phone number via SMS."""
    success = await AuthService(db).send_otp(data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "OTP_LIMIT_REACHED", "message": "Too many OTP requests. Please wait."},
        )
    return MessageResponse(message="OTP sent successfully")


@router.post("/verify-otp", response_model=MessageResponse)
@limiter.limit("5/minute")
async def verify_otp(
    request: Request,
    data: OtpVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Verify the OTP and mark the phone number as verified."""
    verified = await AuthService(db).verify_otp_and_update(data)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OTP_INVALID", "message": "Invalid or expired OTP"},
        )
    return MessageResponse(message="Phone verified successfully")


@router.post("/social-login", response_model=AuthTokensResponse)
async def social_login(
    data: SocialLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthTokensResponse:
    """Login with Google or Apple identity token."""
    return await AuthService(db).social_login(data)
