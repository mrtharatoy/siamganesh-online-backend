"""
Builds the /api/system-status response (SG-B-202), extracted from
core/blueprints/system.py so the route becomes a thin
parse-request/call-service/map-response handler. Logic unchanged.

Takes the Flask app instance explicitly (rather than importing
flask.current_app itself) so this module has no Flask dependency of
its own -- the blueprint is the one running inside a request/app
context and passes `current_app` in.
"""
from datetime import datetime

import psutil

from config import LINE_CHANNEL_ACCESS_TOKEN
from core.repositories.system_status_repository import (
    check_database_health,
    get_supabase_storage_stats,
    get_supabase_usage_metrics,
)


def build_system_status(app):
    uptime = datetime.now() - app.server_start_time
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    db_health = check_database_health()

    apis = {
        "line_notify": bool(LINE_CHANNEL_ACCESS_TOKEN),
        "timezone": "Asia/Bangkok",
    }

    supabase_count, supabase_size = get_supabase_storage_stats("portfolio")
    supabase_size_mb = supabase_size / (1024 * 1024)
    supabase_usage = get_supabase_usage_metrics()

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
            "total_images": supabase_count,
            "total_images_size_mb": round(supabase_size_mb, 2)
        },
        "storage": {
            "supabase": {
                "count": supabase_count,
                "size_mb": round(supabase_size_mb, 2),
                "limit_mb": 1024
            }
        },
        "supabase_usage": {
            "available": supabase_usage["available"],
            "database_size_mb": round(supabase_usage["database_size_bytes"] / (1024 * 1024), 2),
            "database_limit_mb": 500,
            "file_storage_mb": round(supabase_usage["file_storage_bytes"] / (1024 * 1024), 2),
            "file_storage_limit_mb": 1024,
            "file_storage_count": supabase_usage["file_storage_count"],
            "monthly_active_users": supabase_usage["monthly_active_users"],
            "monthly_active_users_limit": 50000,
            "project_ref": _supabase_project_ref(),
        },
        "apis": apis,
    }


def _supabase_project_ref():
    """Derive the safe-to-display Supabase project ref from its URL."""
    from config import SUPABASE_URL

    if not SUPABASE_URL:
        return None
    hostname = SUPABASE_URL.removeprefix("https://").removeprefix("http://").split("/", 1)[0]
    suffix = ".supabase.co"
    return hostname[:-len(suffix)] if hostname.endswith(suffix) else None
