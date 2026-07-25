import os, requests
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

if SUPABASE_URL and SUPABASE_KEY:
    base = SUPABASE_URL.rstrip("/")
    if base.endswith("/rest/v1"):
        url = f"{base}/bookings"
    else:
        url = f"{base}/rest/v1/bookings"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    r = requests.get(f"{url}?limit=1", headers=headers)
    if r.status_code == 200 and r.json():
        print(r.json()[0].keys())
    else:
        print(r.status_code, r.text)
else:
    print("No credentials")
