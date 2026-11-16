"""Email sign-in and the admin second step (Round 8, D5).

Email (public; same answer whether or not the email has an account):
  POST /auth/email/sign-up        email + new password + country -> a code by email
  POST /auth/email/code           "email me a code instead"       -> a code by email
  POST /auth/email/verify         the code -> tokens (creates the account after sign-up)
  POST /auth/password/forgot      -> a reset link by email (30 minutes, once)
  POST /auth/password/reset/check is this reset link still good?
  POST /auth/password/reset       the link's token + a new password; signs out everywhere

Admins, after the first step answered ``mfa_required`` (public: the mfa_token is the proof):
  POST /auth/mfa/verify           authenticator code -> tokens
  POST /auth/mfa/recovery         a recovery code (once each) -> tokens
  POST /auth/mfa/enrol/start      first time: the emailed code -> the authenticator key + QR code
  POST /auth/mfa/enrol/confirm    a code from the app -> tokens + 10 recovery codes (shown once)

Each route has a per-IP ceiling here (high: carrier-grade NAT puts many people behind one
IP) and per-email limits in the service (codes: 1 per 30 s, 5 per hour, 10 per day).
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from core_api.modules.identity.api.v1.auth import limiter
from core_api.modules.identity.schemas.user import (
    AuthTokensResponse,
    EmailCodeRequest,
    EmailSignUpRequest,
    EmailVerifyRequest,
    ForgotPasswordRequest,
    MessageResponse,
    MfaChallengeResponse,
    MfaCodeRequest,
    MfaEnrolledResponse,
    MfaEnrolStartRequest,
    MfaEnrolStartResponse,
    MfaRecoveryRequest,
    PasswordResetRequest,
    ResetTokenRequest,
    ResetTokenStatus,
)
from core_api.modules.identity.service import mfa
from core_api.modules.identity.service.email_auth import EmailAuthService
from shared.db import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]
SignInResult = AuthTokensResponse | MfaChallengeResponse


@router.post("/email/sign-up", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute;300/hour")
async def email_sign_up(request: Request, data: EmailSignUpRequest, db: DB) -> MessageResponse:
    """Start a new account with email + password. A 6-digit code goes to the email;
    the account exists once /auth/email/verify gets it. The same 202 for an email
    that already has an account (that mailbox gets a "you already have an account" email).
    422 PASSWORD_TOO_SHORT / PASSWORD_LIKE_EMAIL / PASSWORD_BREACHED; 429 TOO_MANY_CODES (retry_after)."""
    return MessageResponse(message=await EmailAuthService(db).sign_up(data))


@router.post("/email/code", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute;300/hour")
async def email_code(request: Request, data: EmailCodeRequest, db: DB) -> MessageResponse:
    """Email me a code instead: a sign-in code if the email has an account; the same 202 either way."""
    return MessageResponse(message=await EmailAuthService(db).send_code(data))


@router.post("/email/verify", response_model=SignInResult)
@limiter.limit("30/minute")
async def email_verify(request: Request, data: EmailVerifyRequest, db: DB) -> SignInResult:
    """The emailed code: finishes a sign-up (``is_new_user``) or signs in.
    400 CODE_INVALID (wrong, expired, or used up after 5 wrong tries)."""
    return await EmailAuthService(db).verify(data)


@router.post("/password/forgot", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute;300/hour")
async def password_forgot(request: Request, data: ForgotPasswordRequest, db: DB) -> MessageResponse:
    """Email a link to choose a new password (works once, for 30 minutes; a newer
    link ends the older one). The same 202 whether or not the email has an account."""
    return MessageResponse(message=await EmailAuthService(db).forgot(data))


@router.post("/password/reset/check", response_model=ResetTokenStatus)
@limiter.limit("20/minute")
async def password_reset_check(request: Request, data: ResetTokenRequest, db: DB) -> ResetTokenStatus:
    """Whether a reset link still works (the reset page asks before showing the form)."""
    return ResetTokenStatus(valid=await EmailAuthService(db).reset_valid(data.token))


@router.post("/password/reset", response_model=MessageResponse)
@limiter.limit("10/minute")
async def password_reset(request: Request, data: PasswordResetRequest, db: DB) -> MessageResponse:
    """Set a new password with the link's token; every session ends (sign in again).
    400 RESET_LINK_INVALID; 422 PASSWORD_* (the link keeps working: try another)."""
    await EmailAuthService(db).reset(data)
    return MessageResponse(message="Your password was changed. Sign in with it now.")


@router.post("/mfa/verify", response_model=AuthTokensResponse)
@limiter.limit("10/minute")
async def mfa_verify(request: Request, data: MfaCodeRequest, db: DB) -> AuthTokensResponse:
    """The 6-digit code from the authenticator app. 400 CODE_INVALID; 401 MFA_EXPIRED
    (sign in again); 429 ACCOUNT_LOCKED. A code is never accepted twice."""
    return await mfa.verify_code(db, data.mfa_token, data.code)


@router.post("/mfa/recovery", response_model=AuthTokensResponse)
@limiter.limit("5/minute")
async def mfa_recovery(request: Request, data: MfaRecoveryRequest, db: DB) -> AuthTokensResponse:
    """One of the 10 recovery codes instead of the app (each works once)."""
    return await mfa.verify_recovery(db, data.mfa_token, data.recovery_code)


@router.post("/mfa/enrol/start", response_model=MfaEnrolStartResponse)
@limiter.limit("10/minute")
async def mfa_enrol_start(request: Request, data: MfaEnrolStartRequest, db: DB) -> MfaEnrolStartResponse:
    """First-time set-up: the code emailed with the challenge, then the key to add
    to an authenticator app (QR code and the key as text)."""
    return await mfa.enrol_start(db, data.mfa_token, data.email_code)


@router.post("/mfa/enrol/confirm", response_model=MfaEnrolledResponse)
@limiter.limit("10/minute")
async def mfa_enrol_confirm(request: Request, data: MfaCodeRequest, db: DB) -> MfaEnrolledResponse:
    """A code from the newly added app turns two-step sign-in on and signs in;
    the 10 recovery codes are in the answer and never shown again."""
    return await mfa.enrol_confirm(db, data.mfa_token, data.code)
