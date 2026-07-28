"""
Characterization test for GET /api/system-status.

This route moved to core/blueprints/system.py (SG-B-106). SUPABASE_URL/
SUPABASE_KEY are empty strings in the test environment (conftest.py),
so the database/storage checks inside the route take their documented
"not configured" fallback paths without any network call. This test
locks in the full response shape from API_BASELINE.md #17 so a future
refactor can be diffed against it.

CACHED_FILES/TOTAL_IMAGES_SIZE are patched on core.blueprints.system
(where system_status looks them up from via its image_cache_service
import), not on the app module.
"""
from unittest import mock

import pytest

import core.blueprints.system as system_blueprint


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


def test_system_status_shape_and_fallback_values_when_supabase_not_configured(client):
    # Pin the image-cache globals to a known empty state so this test
    # doesn't depend on execution order relative to other route tests
    # that populate CACHED_FILES/TOTAL_IMAGES_SIZE.
    empty_cache = {"mahabucha": {}, "muteteam": {}, "muteteam_ceremony": {}}
    empty_sizes = {"mahabucha": 0, "muteteam": 0, "muteteam_ceremony": 0}
    with mock.patch.object(system_blueprint, "CACHED_FILES", empty_cache), \
         mock.patch.object(system_blueprint, "TOTAL_IMAGES_SIZE", empty_sizes):
        resp = client.get("/api/system-status")
    assert resp.status_code == 200
    body = resp.get_json()

    assert set(body.keys()) == {"server", "database", "storage", "apis", "jobs"}

    server = body["server"]
    assert set(server.keys()) == {
        "cpu_percent", "ram_percent", "ram_used_mb", "ram_total_mb",
        "disk_percent", "uptime_seconds",
    }
    assert server["uptime_seconds"] >= 0

    # SUPABASE_URL/KEY are empty -> db_status stays "error", counts stay 0.
    assert body["database"] == {
        "status": "error",
        "latency_ms": 0,
        "total_bookings": 0,
        "total_images": 0,
        "total_images_size_mb": 0.0,
    }

    assert body["storage"] == {
        "github": {"count": 0, "size_mb": 0.0, "limit_mb": 1024},
        "supabase": {"count": 0, "size_mb": 0.0, "limit_mb": 1024},
    }

    # GEMINI_API_KEY is empty and LINE/FB tokens come from conftest.
    assert body["apis"] == {
        "gemini_api": False,
        "line_notify": False,
        "timezone": "Asia/Bangkok",
        "fb_graph": True,  # MAHABUCHA_TOKEN/MUTETEAM_TOKEN are set in conftest
    }

    assert set(body["jobs"].keys()) == {"trending_news", "auto_catalog"}
