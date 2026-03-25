from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import require_admin
from app.auth.service import hash_password
from app.auth import supabase_service
from app.storage.supabase_client import client as sb

router_admin = APIRouter(prefix="/admin", tags=["Admin"])


# ── Schemas ─────────────────────────────────────

class OfficerCreate(BaseModel):
    email: str
    password: str
    full_name: str
    rank: Optional[str] = None
    id_number: str
    work_station: str          # "airport", "harbour", etc.
    access_type: str           # "register_and_verify" | "verify_only"


class OfficerUpdate(BaseModel):
    full_name: Optional[str] = None
    rank: Optional[str] = None
    work_station: Optional[str] = None
    access_type: Optional[str] = None
    is_active: Optional[bool] = None


class OfficerOut(BaseModel):
    user_id: int
    email: str
    is_active: bool
    full_name: str
    rank: Optional[str]
    id_number: str
    work_station: str
    access_type: str


# ── CRUD ────────────────────────────────────────

@router_admin.get("/officers", response_model=list[OfficerOut])
async def list_officers(_admin=Depends(require_admin)):
    rows = await sb.get("officers")
    out = []
    for r in rows:
        user = await supabase_service.get_user_by_id(r.get("user_id"))
        out.append(
            OfficerOut(
                user_id=r.get("user_id"),
                email=user.get("email") if user else "",
                is_active=user.get("is_active") if user else False,
                full_name=r.get("full_name"),
                rank=r.get("rank"),
                id_number=r.get("id_number"),
                work_station=r.get("work_station"),
                access_type=r.get("access_type"),
            )
        )
    return out


@router_admin.post("/officers", response_model=OfficerOut, status_code=201)
async def create_officer(body: OfficerCreate, _admin=Depends(require_admin)):
    if body.access_type not in ("register_and_verify", "verify_only"):
        raise HTTPException(status_code=400, detail="access_type must be 'register_and_verify' or 'verify_only'")

    # uniqueness checks
    if await supabase_service.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    if (await sb.get("officers", filters={"id_number": body.id_number})):
        raise HTTPException(status_code=409, detail="ID number already registered")

    user_payload = {
        "email": body.email,
        "password_hash": hash_password(body.password),
        "role": "officer",
        "is_active": True,
    }
    inserted_users = await sb.insert("users", user_payload)
    user = inserted_users[0] if isinstance(inserted_users, list) and inserted_users else inserted_users

    officer_payload = {
        "user_id": user.get("id"),
        "full_name": body.full_name,
        "rank": body.rank,
        "id_number": body.id_number,
        "work_station": body.work_station,
        "access_type": body.access_type,
    }
    inserted = await sb.insert("officers", officer_payload)
    off = inserted[0] if isinstance(inserted, list) and inserted else inserted

    return OfficerOut(
        user_id=user.get("id"),
        email=user.get("email"),
        is_active=user.get("is_active", True),
        full_name=off.get("full_name"),
        rank=off.get("rank"),
        id_number=off.get("id_number"),
        work_station=off.get("work_station"),
        access_type=off.get("access_type"),
    )


@router_admin.get("/officers/{user_id}", response_model=OfficerOut)
async def get_officer(user_id: int, _admin=Depends(require_admin)):
    user = await supabase_service.get_user_by_id(user_id)
    if not user or user.get("role") != "officer":
        raise HTTPException(status_code=404, detail="Officer not found")
    officers = await sb.get("officers", filters={"user_id": user_id})
    if not officers:
        raise HTTPException(status_code=404, detail="Officer not found")
    o = officers[0]
    return OfficerOut(
        user_id=user.get("id"),
        email=user.get("email"),
        is_active=user.get("is_active"),
        full_name=o.get("full_name"),
        rank=o.get("rank"),
        id_number=o.get("id_number"),
        work_station=o.get("work_station"),
        access_type=o.get("access_type"),
    )


@router_admin.patch("/officers/{user_id}", response_model=OfficerOut)
@router_admin.patch("/officers/{user_id}", response_model=OfficerOut)
async def update_officer(user_id: int, body: OfficerUpdate, _admin=Depends(require_admin)):
    user = await supabase_service.get_user_by_id(user_id)
    if not user or user.get("role") != "officer":
        raise HTTPException(status_code=404, detail="Officer not found")
    officers = await sb.get("officers", filters={"user_id": user_id})
    if not officers:
        raise HTTPException(status_code=404, detail="Officer not found")
    o = officers[0]

    officer_updates = {}
    user_updates = {}

    if body.access_type is not None:
        if body.access_type not in ("register_and_verify", "verify_only"):
            raise HTTPException(status_code=400, detail="Invalid access_type")
        officer_updates["access_type"] = body.access_type
    if body.full_name is not None:
        officer_updates["full_name"] = body.full_name
    if body.rank is not None:
        officer_updates["rank"] = body.rank
    if body.work_station is not None:
        officer_updates["work_station"] = body.work_station
    if body.is_active is not None:
        user_updates["is_active"] = body.is_active

    if officer_updates:
        await sb.update("officers", {"user_id": user_id}, officer_updates)
    if user_updates:
        await sb.update("users", {"id": user_id}, user_updates)

    # fetch fresh
    user = await supabase_service.get_user_by_id(user_id)
    officers = await sb.get("officers", filters={"user_id": user_id})
    o = officers[0]

    return OfficerOut(
        user_id=user.get("id"),
        email=user.get("email"),
        is_active=user.get("is_active"),
        full_name=o.get("full_name"),
        rank=o.get("rank"),
        id_number=o.get("id_number"),
        work_station=o.get("work_station"),
        access_type=o.get("access_type"),
    )


@router_admin.delete("/officers/{user_id}")
@router_admin.delete("/officers/{user_id}")
async def delete_officer(user_id: int, _admin=Depends(require_admin)):
    user = await supabase_service.get_user_by_id(user_id)
    if not user or user.get("role") != "officer":
        raise HTTPException(status_code=404, detail="Officer not found")
    await sb.delete("users", {"id": user_id})
    return {"deleted": True, "user_id": user_id}
