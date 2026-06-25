import requests

SUPABASE_URL = "https://dgdbiounzoojphthypfl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnZGJpb3Vuem9vanBodGh5cGZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM4NDY0ODMsImV4cCI6MjA4OTQyMjQ4M30.iTPXmp3SOev5ZxmmpXja0HsBkmB8k5aw8-_7INopOGU"

base = SUPABASE_URL.rstrip("/")
url = f"{base}/storage/v1/object/list/portfolio"
headers = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}"
}
payload = {"prefix": "", "limit": 100, "offset": 0}

r = requests.post(url, headers=headers, json=payload, timeout=10)
print(r.status_code)
print(r.text[:500])
