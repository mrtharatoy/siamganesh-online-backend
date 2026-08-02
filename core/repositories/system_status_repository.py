"""
Read-only Supabase queries backing /api/system-status (SG-B-202),
extracted from core/blueprints/system.py so the route no longer builds
Supabase REST requests inline. Logic unchanged.
"""
import time

import requests

from config import SUPABASE_URL, SUPABASE_KEY


def get_supabase_usage_metrics():
    """Read project-wide usage calculated inside Supabase.

    The RPC is deliberately called with the service-role key from the backend
    only.  It exposes aggregate numbers and never exposes auth users or
    storage object metadata to the browser.
    """
    result = {
        "available": False,
        "database_size_bytes": 0,
        "file_storage_bytes": 0,
        "file_storage_count": 0,
        "monthly_active_users": 0,
    }
    if not (SUPABASE_URL and SUPABASE_KEY):
        return result

    try:
        response = requests.post(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/rpc/get_system_usage_metrics",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
            },
            json={},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        row = payload[0] if isinstance(payload, list) and payload else payload
        if not isinstance(row, dict):
            return result

        for key in ("database_size_bytes", "file_storage_bytes", "file_storage_count", "monthly_active_users"):
            value = row.get(key)
            if isinstance(value, (int, float)):
                result[key] = int(value)
            elif isinstance(value, str) and value.isdigit():
                result[key] = int(value)
        result["available"] = True
    except (requests.RequestException, ValueError, TypeError):
        # The migration may not have been applied yet.  System health must
        # remain available even while the optional usage metrics are absent.
        pass

    return result


def check_database_health():
    """Returns {status, latency_ms, total_bookings}, matching the
    original inline try/except in system_status(): any failure leaves
    status "error" and the other fields at their defaults."""
    result = {"status": "error", "latency_ms": 0, "total_bookings": 0}
    if not (SUPABASE_URL and SUPABASE_KEY):
        return result

    try:
        start_t = time.time()
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/rest/v1/bookings?select=id&limit=1"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        result["latency_ms"] = int((time.time() - start_t) * 1000)
        result["status"] = "ok"

        url_count = f"{base}/rest/v1/bookings?select=id"
        headers_count = headers.copy()
        headers_count["Prefer"] = "count=exact"
        headers_count["Range"] = "0-0"
        r_count = requests.head(url_count, headers=headers_count, timeout=5)
        content_range = r_count.headers.get("Content-Range", "")
        if "/" in content_range:
            result["total_bookings"] = int(content_range.split("/")[1])
    except Exception:
        pass

    return result


def get_supabase_storage_stats(bucket_name, prefix=""):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return 0, 0
    try:
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/storage/v1/object/list/{bucket_name}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        payload = {"prefix": prefix, "limit": 1000, "offset": 0}
        r = requests.post(url, headers=headers, json=payload, timeout=10)

        if r.status_code != 200:
            return 0, 0

        data = r.json()
        count = 0
        size = 0

        for item in data:
            if item.get("id") is None: # It's a folder!
                folder_name = item.get("name")
                if folder_name and folder_name != ".emptyFolderPlaceholder":
                    new_prefix = f"{prefix}{folder_name}/" if prefix else f"{folder_name}/"
                    sub_count, sub_size = get_supabase_storage_stats(bucket_name, new_prefix)
                    count += sub_count
                    size += sub_size
            else: # It's a file
                count += 1
                size += item.get("metadata", {}).get("size", 0)

        return count, size
    except Exception as e:
        print(f"Supabase storage stats error: {e}")
    return 0, 0
