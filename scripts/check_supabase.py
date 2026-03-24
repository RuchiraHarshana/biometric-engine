from dotenv import load_dotenv
import os
import httpx

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
print("SUPABASE_URL:", SUPABASE_URL)
print("KEY_PRESENT:", bool(SUPABASE_KEY))
if not SUPABASE_URL or not SUPABASE_KEY:
    print("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
else:
    url = f"{SUPABASE_URL}/rest/v1/users?select=*"
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Prefer": "return=representation",
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        print("STATUS", resp.status_code)
        print(resp.text[:2000])
    except Exception as e:
        import traceback
        traceback.print_exc()
