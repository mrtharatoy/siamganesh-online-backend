import os
import supabase

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
client = supabase.create_client(url, key)

res = client.table("bookings").select("*").eq("booking_code", "999AA109584").execute()
print(res.data)
