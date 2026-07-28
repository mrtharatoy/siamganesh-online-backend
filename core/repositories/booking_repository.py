"""
Supabase-backed booking/settings queries, extracted from app.py
(SG-B-102). Logic unchanged from the original app.py functions of the
same name -- only the import source for Supabase config moved.

Note: get_supabase_storage_stats() stays in app.py for now -- it is
only used by /api/system-status (SG-B-106 territory), not by anything
moved here.
"""
import requests
from datetime import datetime

from config import SUPABASE_URL, SUPABASE_KEY


def get_booking_by_code(booking_code, owner):
    if not SUPABASE_URL or not SUPABASE_KEY: return None
    try:
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/bookings" if base.endswith("/rest/v1") else f"{base}/rest/v1/bookings"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        params = {"booking_code": f"eq.{booking_code.upper()}", "owner": f"eq.{owner}", "limit": "1"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200 and r.json():
            return r.json()[0]
    except Exception as e:
        print(f"Supabase error get_booking: {e}")
    return None


def get_system_setting(key, default_val=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return default_val
    try:
        base = SUPABASE_URL.rstrip("/")
        url_settings = f"{base}/system_settings" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        r = requests.get(f"{url_settings}?id=eq.{key}&select=value", headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                return data[0].get("value", default_val)
    except Exception as e:
        print(f"Error fetching setting {key}: {e}")
    return default_val


def update_booking_auto_reply_log(booking_id, logs, status_to_set, error_msg=None):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try:
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/bookings?id=eq.{booking_id}" if base.endswith("/rest/v1") else f"{base}/rest/v1/bookings?id=eq.{booking_id}"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}

        current_logs = logs or []
        timestamp_str = datetime.utcnow().isoformat() + "Z"

        if error_msg:
            new_log = {"action": "auto_reply_error", "error": error_msg, "by": "ระบบอัตโนมัติ", "timestamp": timestamp_str}
            payload = {"activity_logs": current_logs + [new_log]}
        else:
            new_log = {"action": status_to_set, "by": "ระบบอัตโนมัติ", "timestamp": timestamp_str}
            payload = {"status": status_to_set, "activity_logs": current_logs + [new_log]}

        requests.patch(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"Supabase error update log: {e}")


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
