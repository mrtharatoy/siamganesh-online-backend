"""
Tests for core/services/system_status_service.py (SG-B-202).
build_system_status() takes an app-like object explicitly rather than
using flask.current_app, so it can be tested with a plain stub instead
of a real Flask request context.
"""
from datetime import datetime, timedelta
from unittest import mock

import core.services.system_status_service as service


class _FakeApp:
    def __init__(self, server_start_time):
        self.server_start_time = server_start_time


def test_build_system_status_shape_and_defaults():
    fake_app = _FakeApp(server_start_time=datetime.now() - timedelta(seconds=5))

    with mock.patch.object(service, "CACHED_FILES", {"mahabucha": {}, "muteteam": {}}), \
         mock.patch.object(service, "TOTAL_IMAGES_SIZE", {"mahabucha": 0, "muteteam": 0}), \
         mock.patch.object(service, "check_database_health",
                            return_value={"status": "error", "latency_ms": 0, "total_bookings": 0}), \
         mock.patch.object(service, "get_supabase_storage_stats", return_value=(0, 0)):
        result = service.build_system_status(fake_app)

    assert set(result.keys()) == {"server", "database", "storage", "apis", "jobs"}
    assert result["server"]["uptime_seconds"] >= 5
    assert result["database"] == {
        "status": "error", "latency_ms": 0, "total_bookings": 0,
        "total_images": 0, "total_images_size_mb": 0.0,
    }
    assert result["jobs"] == {"auto_catalog": None}


def test_build_system_status_combines_github_and_supabase_image_totals():
    fake_app = _FakeApp(server_start_time=datetime.now())

    with mock.patch.object(service, "CACHED_FILES", {"mahabucha": {"a": "a.jpg"}, "muteteam": {"b": "b.jpg", "c": "c.jpg"}}), \
         mock.patch.object(service, "TOTAL_IMAGES_SIZE", {"mahabucha": 1024 * 1024, "muteteam": 0}), \
         mock.patch.object(service, "check_database_health",
                            return_value={"status": "ok", "latency_ms": 12, "total_bookings": 5}), \
         mock.patch.object(service, "get_supabase_storage_stats", return_value=(4, 2 * 1024 * 1024)):
        result = service.build_system_status(fake_app)

    assert result["storage"]["github"]["count"] == 3  # 1 mahabucha + 2 muteteam
    assert result["storage"]["github"]["size_mb"] == 1.0
    assert result["storage"]["supabase"]["count"] == 4
    assert result["storage"]["supabase"]["size_mb"] == 2.0
    assert result["database"]["total_images"] == 7  # 3 github + 4 supabase
    assert result["database"]["total_images_size_mb"] == 3.0
