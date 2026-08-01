"""
Supabase-backed booking/settings queries, extracted from app.py
(SG-B-102). Logic unchanged from the original app.py functions of the
same name -- only the import source for Supabase config moved.

Note: get_supabase_storage_stats() stays in app.py for now -- it is
only used by /api/system-status (SG-B-106 territory), not by anything
moved here.
"""
import requests

from config import SUPABASE_URL, SUPABASE_KEY


def get_booking_names(booking_code):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None, None
    try:
        base = SUPABASE_URL.rstrip("/")
        if base.endswith("/rest/v1"):
            url = f"{base}/bookings"
        else:
            url = f"{base}/rest/v1/bookings"
        headers = {
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        params = {
            "select":       "person1_name,person2_name",
            "booking_code": f"eq.{booking_code}",
            "limit":        "1",
        }
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200 and r.json():
            row = r.json()[0]
            return row.get("person1_name"), row.get("person2_name")
    except Exception as e:
        print(f"Supabase error: {e}")
    return None, None
