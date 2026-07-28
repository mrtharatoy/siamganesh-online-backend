"""
Search/System blueprint (SG-B-106), extracted from app.py:
`/api/search`, `/api/system-status`. Route logic is unchanged from the
original app.py handlers of the same name -- only the import source
moved.

Two things needed special handling to avoid a circular import back to
app.py, since this blueprint has no direct reference to the module-level
`app` object app.py creates:

- SERVER_START_TIME used to be a plain module-level datetime in app.py.
  It's now set as `app.server_start_time` right after the Flask app is
  constructed (the exact same timing as before), and read here via
  `flask.current_app` -- the same "attach runtime metadata to the app
  instance" pattern app.py's scheduler functions already use for
  `last_trending_news_time`.
- `last_trending_news_time`/`last_auto_catalog_time` are read the same
  way, via `current_app` instead of a direct `app` reference.
  `last_auto_catalog_time` is never actually set anywhere in this
  codebase (pre-existing, documented in API_BASELINE.md) -- it stays
  permanently None, unchanged from before this move.
"""
import os
import time

import psutil
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

from config import (
    SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY,
    LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA, LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM,
)
from core.services.image_cache_service import CACHED_FILES, TOTAL_IMAGES_SIZE, lock, is_loaded, update_file_list, get_image_url

system_bp = Blueprint("system", __name__)


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


@system_bp.route('/api/search', methods=['GET'])
def search_api():
    page = request.args.get('page', '').lower()
    code = request.args.get('code', '').lower().strip()

    if page not in ["mahabucha", "muteteam", "muteteam_ceremony"] or not code:
        return jsonify({"found": False, "message": "ข้อมูลไม่ครบ"}), 400

    if not is_loaded():
        with lock:
            if not is_loaded():
                update_file_list()

    current_cache = CACHED_FILES.get(page, {})

    if page == "muteteam":
        matched = [
            {"code": key.upper(), "image_url": get_image_url(page, filename)}
            for key, filename in sorted(current_cache.items())
            if key.startswith(code)
        ]
        if matched:
            return jsonify({"found": True, "results": matched, "count": len(matched)}), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404
    else:
        if code in current_cache:
            return jsonify({
                "found": True,
                "code": code.upper(),
                "image_url": get_image_url(page, current_cache[code])
            }), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404


@system_bp.route('/api/system-status', methods=['GET'])
def system_status():
    uptime = datetime.now() - current_app.server_start_time
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # DB connection check
    db_status = "error"
    db_latency = 0
    total_bookings = 0
    if SUPABASE_URL and SUPABASE_KEY:
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
            db_latency = int((time.time() - start_t) * 1000)
            db_status = "ok"

            # Get total count
            url_count = f"{base}/rest/v1/bookings?select=id"
            headers_count = headers.copy()
            headers_count["Prefer"] = "count=exact"
            headers_count["Range"] = "0-0"
            r_count = requests.head(url_count, headers=headers_count, timeout=5)
            content_range = r_count.headers.get("Content-Range", "")
            if "/" in content_range:
                total_bookings = int(content_range.split("/")[1])
        except Exception:
            pass

    # External APIs check
    apis = {
        "gemini_api": bool(GEMINI_API_KEY),
        "line_notify": bool(LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA or LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM),
        "timezone": "Asia/Bangkok",
        "fb_graph": bool(os.environ.get('MUTETEAM_TOKEN') or os.environ.get('MAHABUCHA_TOKEN'))
    }

    # Background Jobs info
    jobs = {
        "trending_news": getattr(current_app, 'last_trending_news_time', None),
        "auto_catalog": getattr(current_app, 'last_auto_catalog_time', None),
    }

    total_images_github = len(CACHED_FILES.get("mahabucha", {})) + len(CACHED_FILES.get("muteteam", {}))
    total_images_size_github_mb = (TOTAL_IMAGES_SIZE.get("mahabucha", 0) + TOTAL_IMAGES_SIZE.get("muteteam", 0)) / (1024 * 1024)

    supabase_count, supabase_size = get_supabase_storage_stats("portfolio")
    supabase_size_mb = supabase_size / (1024 * 1024)

    total_images = total_images_github + supabase_count
    total_images_size_mb = total_images_size_github_mb + supabase_size_mb

    return jsonify({
        "server": {
            "cpu_percent": cpu_percent,
            "ram_percent": mem.percent,
            "ram_used_mb": mem.used // (1024*1024),
            "ram_total_mb": mem.total // (1024*1024),
            "disk_percent": disk.percent,
            "uptime_seconds": uptime.total_seconds()
        },
        "database": {
            "status": db_status,
            "latency_ms": db_latency,
            "total_bookings": total_bookings,
            "total_images": total_images,
            "total_images_size_mb": round(total_images_size_mb, 2)
        },
        "storage": {
            "github": {
                "count": total_images_github,
                "size_mb": round(total_images_size_github_mb, 2),
                "limit_mb": 1024
            },
            "supabase": {
                "count": supabase_count,
                "size_mb": round(supabase_size_mb, 2),
                "limit_mb": 1024
            }
        },
        "apis": apis,
        "jobs": jobs
    }), 200
