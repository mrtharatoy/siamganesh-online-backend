import os
from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

try:
    res = supabase.table("objects").select("id, metadata").eq("bucket_id", "portfolio").execute()
    print("Default schema:", len(res.data))
except Exception as e:
    print("Default schema failed:", e)

try:
    supabase.schema("storage")
    res = supabase.schema("storage").table("objects").select("id, metadata").eq("bucket_id", "portfolio").execute()
    count = len(res.data)
    size = sum(item.get("metadata", {}).get("size", 0) for item in res.data)
    print("Storage schema count:", count)
    print("Storage schema size:", size)
except Exception as e:
    print("Storage schema failed:", e)

