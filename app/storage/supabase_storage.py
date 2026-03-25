import httpx
from app.core.config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_BUCKET

SUPABASE_STORAGE_URL = f"{SUPABASE_URL}/storage/v1"


async def upload_face_image(person_id: str, image_bytes: bytes, content_type: str | None) -> tuple[str, str]:
    file_ext = "jpg"
    if content_type and "png" in content_type:
        file_ext = "png"
    key = f"faces/{person_id}.{file_ext}"
    url = f"{SUPABASE_STORAGE_URL}/object/{SUPABASE_BUCKET}/{key}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": content_type or "application/octet-stream",
        "x-upsert": "true",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, content=image_bytes, headers=headers)
        resp.raise_for_status()
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{key}"
    return key, public_url


async def delete_face_image(key: str) -> None:
    url = f"{SUPABASE_STORAGE_URL}/object/{SUPABASE_BUCKET}/{key}"
    headers = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
