from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.service import decode_token
from app.auth import supabase_service
from app.core.config import SKIP_2FA

_bearer = HTTPBearer()


async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    payload = decode_token(creds.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if not SKIP_2FA and not payload.get("2fa_verified"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="2FA not verified")

    user = await supabase_service.get_user_by_id(payload.get("sub"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_officer(user=Depends(get_current_user)):
    if user.get("role") not in ("admin", "officer"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Officer access required")
    return user


async def require_register_access(user=Depends(get_current_user)):
    if user.get("role") == "admin":
        return user
    if user.get("role") == "officer":
        officer = await supabase_service.get_officer_by_user_id(user.get("id"))
        if officer and officer.get("access_type") == "register_and_verify":
            return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Registration access required")


async def require_verify_access(user=Depends(get_current_user)):
    if user.get("role") == "admin":
        return user
    if user.get("role") == "officer":
        officer = await supabase_service.get_officer_by_user_id(user.get("id"))
        if officer and officer.get("access_type") in ("verify_only", "register_and_verify"):
            return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification access required")
