import os
import requests

with open('.env') as f:
    for line in f:
        if line.startswith('SUPABASE_URL='):
            SUPABASE_URL = line.strip().split('=', 1)[1]
        elif line.startswith('SUPABASE_KEY='):
            SUPABASE_KEY = line.strip().split('=', 1)[1]

base = SUPABASE_URL.rstrip("/")
# Storage is usually at /storage/v1
storage_base = f"{base}/storage/v1"
headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

url = f"{storage_base}/object/list/portfolio"
payload = {"prefix": "", "limit": 100, "offset": 0, "sortBy": {"column": "name", "order": "asc"}}

r = requests.post(url, headers=headers, json=payload)
print("Status Code:", r.status_code)
if r.status_code == 200:
    data = r.json()
    count = len(data)
    size = sum(item.get("metadata", {}).get("size", 0) for item in data)
    print("Count:", count)
    print("Size:", size)
else:
    print("Response:", r.text[:200])

