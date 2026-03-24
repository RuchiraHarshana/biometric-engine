"""Seed the initial admin user via Supabase.

Usage:
    python -m scripts.seed_admin --email admin@biosecuregate.com --password <password>

This script creates an `admin` user in the Supabase `users` table.
"""
import argparse
import asyncio
import httpx

from app.storage.supabase_client import client as sb
from app.auth.service import hash_password


async def seed_admin(email: str, password: str):
    existing = await sb.get("users", filters={"email": email})
    if existing:
        print(f"User {email} already exists (role={existing[0].get('role')}).")
        return

    payload = {
        "email": email,
        "password_hash": hash_password(password),
        "role": "admin",
        "is_active": True,
    }
    try:
        await sb.insert("users", payload)
        print(f"Admin user created: {email}")
    except httpx.HTTPStatusError as exc:
        # handle duplicate primary key sequence mismatch by retrying with an explicit id
        if exc.response is not None and exc.response.status_code == 409:
            users = await sb.get("users", select="id")
            max_id = 0
            for u in users:
                try:
                    uid = int(u.get("id", 0))
                    if uid > max_id:
                        max_id = uid
                except Exception:
                    continue
            payload["id"] = max_id + 1
            await sb.insert("users", payload)
            print(f"Admin user created with id {payload['id']}: {email}")
        else:
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(seed_admin(args.email, args.password))
