from typing import Optional, Dict, Any

from app.storage.supabase_client import client as sb
from app.auth import service as auth_service


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    rows = await sb.get("users", filters={"email": email})
    return rows[0] if rows else None


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    rows = await sb.get("users", filters={"id": user_id})
    return rows[0] if rows else None


async def authenticate_user_supabase(email: str, password: str) -> Optional[Dict[str, Any]]:
    user = await get_user_by_email(email)
    if not user:
        return None
    hashed = user.get("password_hash")
    if auth_service.verify_password(password, hashed):
        return user
    return None


async def get_officer_by_user_id(user_id: int) -> Optional[Dict[str, Any]]:
    rows = await sb.get("officers", filters={"user_id": user_id})
    return rows[0] if rows else None


async def set_totp_secret(user_id: int, secret: str) -> None:
    await sb.update("users", {"id": user_id}, {"totp_secret": secret})


async def set_totp_verified(user_id: int, verified: bool = True) -> None:
    await sb.update("users", {"id": user_id}, {"totp_verified": verified})

