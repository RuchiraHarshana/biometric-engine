import asyncio
from app.storage.supabase_client import client as sb


async def main():
    print("Users:")
    users = await sb.get("users")
    for u in users:
        print(f"- {u.get('id')}: {u.get('email')} | role={u.get('role')} | active={u.get('is_active')}")

    print("\nOfficers:")
    officers = await sb.get("officers")
    for o in officers:
        print(f"- {o.get('id')}: {o.get('full_name')} | user_id={o.get('user_id')} | id_number={o.get('id_number')} | station={o.get('work_station')}")


if __name__ == "__main__":
    asyncio.run(main())
