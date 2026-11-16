from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from shared.auth import BearerAuth
from shared.client_ip import client_ip
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import get_current_active_user
from shared.db import get_db
from core_api.modules.identity.models.user import User
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    MfaChallengeResponse,
    LoginRequest,
    MessageResponse,
    OtpSendRequest,
    OtpVerifyRequest,
    PhoneSignInRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SocialLoginRequest,
)
from core_api.modules.identity.service.auth import AuthService
from core_api.modules.legal import service as legal

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = structlog.get_logger(__name__)
limiter = Limiter(key_func=client_ip)
security = BearerAuth()


SignInResult = AuthTokensResponse | MfaChallengeResponse


@router.post("/login", response_model=SignInResult)
# Per IP only a high ceiling (many people share an IP behind carrier-grade NAT); each
# account locks after 5 wrong passwords (service/guard.py).
@limiter.limit("30/minute;300/hour")
async def login(
    request: Request,
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> SignInResult:
    """Sign in with email and password.

    401 INVALID_CREDENTIALS for an unknown email and a wrong password alike;
    429 ACCOUNT_LOCKED (``retry_after`` seconds) after 5 wrong tries in 15 minutes.
    Admins get MfaChallengeResponse (``mfa_required``): finish at /auth/mfa/*."""
    return await AuthService(db).login(data)


@router.post("/refresh", response_model=AuthTokensResponse)
async def refresh_token(
    data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AuthTokensResponse:
    """Exchange a refresh token for a new access + refresh token pair."""
    return await AuthService(db).refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MessageResponse:
    """Logout — invalidates the current access token and all refresh tokens."""
    await AuthService(db).logout(credentials.credentials, str(current_user.id))
    return MessageResponse(message="Logged out successfully")


@router.post("/send-otp", response_model=MessageResponse)
# Limited per phone number (1 per 30 s, 5 per hour, 10 per day: 429 TOO_MANY_CODES with
# retry_after); per IP only a high ceiling against abuse (carrier-grade NAT shares IPs).
@limiter.limit("30/minute;300/hour")
async def send_otp(
    request: Request,
    data: OtpSendRequest,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MessageResponse:
    """Send a 6-digit OTP to the given phone number via SMS.
    429 TOO_MANY_CODES (``retry_after`` seconds) when this number had too many codes lately;
    503 SEND_FAILED when the SMS provider didn't take it."""
    success = await AuthService(db).send_otp(data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SEND_FAILED", "message": "We couldn't send the code. Try again in a moment."},
        )
    return MessageResponse(message="OTP sent successfully")


@router.post("/verify-otp", response_model=MessageResponse)
@limiter.limit("30/minute")
async def verify_otp(
    request: Request,
    data: OtpVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MessageResponse:
    """Verify the OTP and mark the phone number as verified."""
    verified = await AuthService(db).verify_otp_and_update(data)
    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OTP_INVALID", "message": "Invalid or expired OTP"},
        )
    return MessageResponse(message="Phone verified successfully")


@router.post("/phone", response_model=SignInResult)
@limiter.limit("30/minute")
async def phone_sign_in(
    request: Request,
    data: PhoneSignInRequest,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> SignInResult:
    """Sign in with the SMS code from /auth/send-otp. A new number gets a
    customer account (``is_new_user`` is true; ask for their name next)."""
    return await AuthService(db).phone_sign_in(data, legal.client_info(request))


@router.get("/jwks", tags=["Authentication"])
async def jwks_alias() -> dict:
    """Same as /.well-known/jwks.json."""
    from shared import jwt_keys

    return jwt_keys.jwks()


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MessageResponse:
    """Reset a forgotten password using an OTP sent to the account's phone number.

    Flow: client calls /auth/send-otp, then submits the OTP + new password here.
    422 PASSWORD_* when the new password breaks a rule (service/passwords.py).
    Ends every session. By email instead: /auth/password/forgot.
    """
    await AuthService(db).reset_password(data)
    return MessageResponse(message="Password reset successfully")


class ProviderClient(BaseModel):
    client_id: str


class SignInProviders(BaseModel):
    """Which "Sign in with ..." buttons to show: null = not configured (hide it)."""

    google: ProviderClient | None = None
    apple: ProviderClient | None = None


@router.get("/providers", response_model=SignInProviders)
async def sign_in_providers() -> SignInProviders:
    """Public: the social sign-in providers this environment accepts, with the
    website's OAuth client id (public by nature). Send the provider's ID token
    to POST /auth/social-login."""
    from shared.config import get_settings

    ident = get_settings().identity
    google = ident.google_web_client_id
    return SignInProviders(google=ProviderClient(client_id=google) if google else None,
                           apple=ProviderClient(client_id=ident.APPLE_CLIENT_ID) if ident.APPLE_CLIENT_ID else None)


@router.post("/social-login", response_model=SignInResult)
@limiter.limit("30/minute")
async def social_login(
    request: Request,
    data: SocialLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> SignInResult:
    """Sign in with a Google or Apple ID token (the website's Google button sends
    the Google Identity Services credential). The token is verified against the
    provider's public keys, issuer and our client ids; the account is found by
    provider id, else linked by a verified email, else created (customer).
    401 INVALID_GOOGLE_TOKEN / INVALID_APPLE_TOKEN, also when the provider isn't configured."""
    return await AuthService(db).social_login(data, legal.client_info(request))
