"""
Builds the /api/system-status response (SG-B-202), extracted from
core/blueprints/system.py so the route becomes a thin
parse-request/call-service/map-response handler. Logic unchanged.

Takes the Flask app instance explicitly (rather than importing
flask.current_app itself) so this module has no Flask dependency of
its own -- the blueprint is the one running inside a request/app
context and passes `current_app` in.
"""
import os
from datetime import datetime

import psutil

from config import LINE_CHANNEL_ACCESS_TOKEN
from core.repositories.system_status_repository import check_database_health, get_supabase_storage_stats
from core.services.image_cache_service import CACHED_FILES, TOTAL_IMAGES_SIZE


def build_system_status(app):
    uptime = datetime.now() - app.server_start_time
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    db_health = check_database_health()

    apis = {
        "line_notify": bool(LINE_CHANNEL_ACCESS_TOKEN),
        "timezone": "Asia/Bangkok",
        "fb_graph": bool(os.environ.get('MUTETEAM_TOKEN') or os.environ.get('MAHABUCHA_TOKEN'))
    }

    # trending_news removed with the AI trending-news feature (SG-B-2xx);
    # auto_catalog is a legacy field that was never actually set anywhere
    # in this codebase (always null) -- kept as-is, not this refactor's scope.
    jobs = {
        "auto_catalog": getattr(app, 'last_auto_catalog_time', None),
    }

    total_images_github = len(CACHED_FILES.get("mahabucha", {})) + len(CACHED_FILES.get("muteteam", {}))
    total_images_size_github_mb = (TOTAL_IMAGES_SIZE.get("mahabucha", 0) + TOTAL_IMAGES_SIZE.get("muteteam", 0)) / (1024 * 1024)

    supabase_count, supabase_size = get_supabase_storage_stats("portfolio")
    supabase_size_mb = supabase_size / (1024 * 1024)

    total_images = total_images_github + supabase_count
    total_images_size_mb = total_images_size_github_mb + supabase_size_mb

    return {
        "server": {
            "cpu_percent": cpu_percent,
            "ram_percent": mem.percent,
            "ram_used_mb": mem.used // (1024*1024),
            "ram_total_mb": mem.total // (1024*1024),
            "disk_percent": disk.percent,
            "uptime_seconds": uptime.total_seconds()
        },
        "database": {
            "status": db_health["status"],
            "latency_ms": db_health["latency_ms"],
            "total_bookings": db_health["total_bookings"],
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
    }
