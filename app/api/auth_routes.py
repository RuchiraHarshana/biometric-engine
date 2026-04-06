from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from app.auth import supabase_service
from app.auth.service import (
    create_access_token,
    decode_token,
    generate_totp_secret,
    get_totp_uri,
    verify_totp,
)
from app.auth.dependencies import get_current_user
from app.core.config import SKIP_2FA
from app.utils.email import send_email
import random
from datetime import datetime


router_auth = APIRouter(prefix="/auth", tags=["Auth"])
_bearer = HTTPBearer()
_bearer_optional = HTTPBearer(auto_error=False)


# ── Schemas ─────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    temp_token: str
    requires_2fa_setup: bool
    message: str
    email: Optional[str] = None


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    message: str


class TotpVerifyRequest(BaseModel):
    code: str
    email: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str
    access_type: Optional[str] = None


async def _get_user_from_temp_token(creds: HTTPAuthorizationCredentials):
    """Validate a temporary token (2FA not yet verified)."""
    payload = decode_token(creds.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = await supabase_service.get_user_by_id(payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ── Login (step 1) ──────────────────────────────

@router_auth.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    user = await supabase_service.authenticate_user_supabase(body.email, body.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    # If the user has TOTP configured (has secret) and 2FA isn't skipped, continue with TOTP flow
    # If a record says `totp_verified` but there's no `totp_secret`, fall back to email OTP.
    if not SKIP_2FA and user.get("totp_verified") and user.get("totp_secret"):
        temp_token = create_access_token(
            {"sub": user.get("id"), "role": user.get("role"), "2fa_verified": False},
            expires_minutes=10,
        )
        return LoginResponse(
            temp_token=temp_token,
            requires_2fa_setup=False,
            message="Enter your 2FA code",
            email=user.get("email"),
        )

    # Otherwise use email OTP: generate a 6-digit code and a short-lived token, send email
    code = f"{random.randint(0, 999999):06d}"
    otp_token = create_access_token({"email": user.get("email"), "otp": code, "type": "email_otp"}, expires_minutes=5)
    subject = "Your BioSecureGate login code"
    body_text = f"Your login verification code is: {code}\nIt expires in 5 minutes."
    # DEBUG: print the OTP to server logs to help testing (remove in production)
    print(f"DEBUG OTP -> email={user.get('email')} code={code} token={otp_token}")
    try:
        send_email(user.get("email"), subject, body_text)
    except Exception as e:
        print("send_email failed:", repr(e))

    return LoginResponse(
        temp_token=otp_token,
        requires_2fa_setup=False,
        message="Enter the 6-digit code sent to your email",
        email=user.get("email"),
    )


# ── 2FA setup (first time only) ────────────────

@router_auth.post("/2fa/setup", response_model=TotpSetupResponse)
async def setup_2fa(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    user = await _get_user_from_temp_token(creds)

    if user.get("totp_verified"):
        raise HTTPException(status_code=400, detail="2FA already configured")

    secret = generate_totp_secret()
    await supabase_service.set_totp_secret(user.get("id"), secret)

    uri = get_totp_uri(secret, user.get("email"))
    return TotpSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        message="Scan QR code with authenticator app, then verify with /auth/2fa/verify",
    )


# ── 2FA verify (step 2 of login) ───────────────

@router_auth.post("/2fa/verify", response_model=TokenResponse)
async def verify_2fa(
    body: TotpVerifyRequest,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_optional),
):
    user = None

    # Try token-based auth first
    if creds:
        payload = decode_token(creds.credentials)
        if payload:
            # Support email OTP tokens (issued at login) which contain 'type':'email_otp'
            if payload.get("type") == "email_otp":
                # verify OTP code embedded in token
                if payload.get("otp") != body.code:
                    raise HTTPException(status_code=401, detail="Invalid 2FA code")
                user = await supabase_service.get_user_by_email(payload.get("email"))
                if user is None:
                    raise HTTPException(status_code=401, detail="User not found")
                # mark totp_verified flag for consistency (optional)
                if not user.get("totp_verified"):
                    await supabase_service.set_totp_verified(user.get("id"), True)
                # Fetch access_type for officers
                officer_access_type = None
                if user.get("role") == "officer":
                    officer = await supabase_service.get_officer_by_user_id(user.get("id"))
                    if officer:
                        officer_access_type = officer.get("access_type")
                access_token = create_access_token({"sub": user.get("id"), "role": user.get("role"), "2fa_verified": True, **({
                    "access_type": officer_access_type} if officer_access_type else {})},)
                return TokenResponse(access_token=access_token, role=user.get("role"), email=user.get("email"), access_type=officer_access_type)
            # else: standard TOTP token path uses 'sub'
            user = await supabase_service.get_user_by_id(payload.get("sub"))

    # Fallback: look up by email when SKIP_2FA is on and token is missing/expired
    if user is None and SKIP_2FA and body.email:
        user = await supabase_service.get_user_by_email(body.email)

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not SKIP_2FA:
        if not user.get("totp_secret"):
            raise HTTPException(status_code=400, detail="2FA not set up. Call /auth/2fa/setup first")

        if not verify_totp(user.get("totp_secret"), body.code):
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

    if not user.get("totp_verified"):
        await supabase_service.set_totp_verified(user.get("id"), True)

    # Fetch access_type for officers
    officer_access_type = None
    if user.get("role") == "officer":
        officer = await supabase_service.get_officer_by_user_id(user.get("id"))
        if officer:
            officer_access_type = officer.get("access_type")

    token_data = {"sub": user.get("id"), "role": user.get("role"), "2fa_verified": True}
    if officer_access_type:
        token_data["access_type"] = officer_access_type

    access_token = create_access_token(token_data)
    return TokenResponse(access_token=access_token, role=user.get("role"), email=user.get("email"), access_type=officer_access_type)


# ── Email OTP (send & verify) ──────────────────────────────


class OtpSendRequest(BaseModel):
    email: str


class OtpVerifyRequest(BaseModel):
    token: str
    code: str


@router_auth.post("/otp/send")
async def otp_send(body: OtpSendRequest):
    user = await supabase_service.get_user_by_email(body.email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # generate 6-digit numeric code
    code = f"{random.randint(0, 999999):06d}"
    # create short-lived token embedding the code and email
    otp_token = create_access_token({"email": body.email, "otp": code, "type": "email_otp"}, expires_minutes=5)

    # send via SMTP; if SMTP not configured, send_email will print to console
    subject = "Your BioSecureGate OTP code"
    body_text = f"Your verification code is: {code}\nIt expires in 5 minutes.\nIf you did not request this, ignore."
    try:
        send_email(body.email, subject, body_text)
    except Exception as e:
        print("Failed to send email:", e)

    # For dev convenience, return token presence indicator (helps testing). Do NOT return the code in production.
    return {"sent": True, "otp_token": otp_token}


@router_auth.post("/otp/verify", response_model=TokenResponse)
async def otp_verify(body: OtpVerifyRequest):
    payload = decode_token(body.token)
    if not payload or payload.get("type") != "email_otp":
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if payload.get("otp") != body.code:
        raise HTTPException(status_code=401, detail="Invalid code")

    email = payload.get("email")
    user = await supabase_service.get_user_by_email(email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Fetch access_type for officers
    officer_access_type = None
    if user.get("role") == "officer":
        officer = await supabase_service.get_officer_by_user_id(user.get("id"))
        if officer:
            officer_access_type = officer.get("access_type")

    token_data = {"sub": user.get("id"), "role": user.get("role"), "2fa_verified": True}
    if officer_access_type:
        token_data["access_type"] = officer_access_type

    access_token = create_access_token(token_data)
    return TokenResponse(access_token=access_token, role=user.get("role"), email=user.get("email"), access_type=officer_access_type)


# ── Who am I ────────────────────────────────────

@router_auth.get("/me")
async def me(user=Depends(get_current_user)):
    result = {
        "id": user.get("id"),
        "email": user.get("email"),
        "role": user.get("role"),
        "totp_verified": user.get("totp_verified"),
    }
    # Include access_type for officers
    if user.get("role") == "officer":
        officer = await supabase_service.get_officer_by_user_id(user.get("id"))
        if officer:
            result["access_type"] = officer.get("access_type")
    return result
