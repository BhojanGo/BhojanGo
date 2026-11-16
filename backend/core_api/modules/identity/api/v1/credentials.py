"""Sign-in and security for the signed-in person (Round 8, D5):

  GET  /me/security                 how this account signs in
  POST /me/password                 set or change the password (signs out every other device)
  POST /me/email  /me/email/verify  link an email, verified by a code
  POST /me/phone  /me/phone/verify  link a phone, verified by an SMS code
  POST /me/mfa/recovery-codes       admins: new recovery codes (needs an authenticator code)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.dependencies import get_current_active_user, security
from core_api.modules.identity.api.v1.auth import limiter
from core_api.modules.identity.models.user import User
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    ChangePasswordRequest,
    LinkEmailStart,
    LinkEmailVerify,
    LinkPhoneStart,
    LinkPhoneVerify,
    MessageResponse,
    RecoveryCodesRenewRequest,
    RecoveryCodesResponse,
    SecurityOverview,
    UserResponse,
)
from core_api.modules.identity.service import mfa
from core_api.modules.identity.service.credentials import CredentialsService
from shared.db import get_db

router = APIRouter(prefix="/me", tags=["Account"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
Me = Annotated[User, Depends(get_current_active_user)]
Token = Annotated[HTTPAuthorizationCredentials, Depends(security)]


@router.get("/security", response_model=SecurityOverview)
async def security_overview(me: Me, db: DB) -> SecurityOverview:
    return await CredentialsService(db, me).overview()


@router.post("/password", response_model=AuthTokensResponse)
@limiter.limit("10/minute")
async def change_password(request: Request, data: ChangePasswordRequest, me: Me, token: Token,
                          db: DB) -> AuthTokensResponse:
    """Set a first password (an email is needed) or change it (with the current one).
    Every other device is signed out; this one gets the new tokens in the answer.
    400 WRONG_PASSWORD; 409 EMAIL_REQUIRED; 422 PASSWORD_*; 429 ACCOUNT_LOCKED."""
    return await CredentialsService(db, me).change_password(data, token.credentials)


@router.post("/email", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def link_email(request: Request, data: LinkEmailStart, me: Me, db: DB) -> MessageResponse:
    """Send a code to the email to link. 409 EMAIL_IN_USE (another account has it) / ALREADY_LINKED."""
    await CredentialsService(db, me).start_email(data)
    return MessageResponse(message="We sent a 6-digit code to that email.")


@router.post("/email/verify", response_model=UserResponse)
@limiter.limit("10/minute")
async def link_email_verify(request: Request, data: LinkEmailVerify, me: Me, db: DB) -> UserResponse:
    return UserResponse.model_validate(await CredentialsService(db, me).verify_email(data))


@router.post("/phone", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("3/minute")
async def link_phone(request: Request, data: LinkPhoneStart, me: Me, db: DB) -> MessageResponse:
    """Send an SMS code to the number to link. 409 PHONE_IN_USE / ALREADY_LINKED."""
    await CredentialsService(db, me).start_phone(data)
    return MessageResponse(message="We sent a 6-digit code to that number.")


@router.post("/phone/verify", response_model=UserResponse)
@limiter.limit("10/minute")
async def link_phone_verify(request: Request, data: LinkPhoneVerify, me: Me, db: DB) -> UserResponse:
    return UserResponse.model_validate(await CredentialsService(db, me).verify_phone(data))


@router.post("/mfa/recovery-codes", response_model=RecoveryCodesResponse)
@limiter.limit("5/minute")
async def renew_recovery_codes(request: Request, data: RecoveryCodesRenewRequest, me: Me,
                               db: DB) -> RecoveryCodesResponse:
    """Ten new recovery codes (the old ones stop working). Needs a code from the authenticator app."""
    return RecoveryCodesResponse(recovery_codes=await mfa.renew_recovery_codes(db, me, data.code))
