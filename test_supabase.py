import os
import requests
from datetime import datetime

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def log_debug(message):
    base = SUPABASE_URL.rstrip("/")
    url = f"{base}/system_settings" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings"
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
    
    # Try to insert or update
    # Using upsert
    payload = {
        "id": "debug_webhook",
        "value": {"last_log": message, "time": datetime.utcnow().isoformat()}
    }
    r = requests.post(url, headers=headers, json=payload, headers={"Prefer": "resolution=merge-duplicates", **headers})
    print(r.status_code, r.text)

log_debug("test")
