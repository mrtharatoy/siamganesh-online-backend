"""
Characterization tests for GET /api/search (SG-B-106). No test
previously existed for this route. CACHED_FILES is patched on
core.blueprints.system (where search_api looks it up from via its
image_cache_service import), not on the app module.
"""
from unittest import mock

import pytest

import core.blueprints.system as system_blueprint


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


def test_search_400_when_page_invalid_or_code_missing(client):
    resp = client.get("/api/search", query_string={"page": "not-a-real-page", "code": "x"})
    assert resp.status_code == 400
    assert resp.get_json() == {"found": False, "message": "ข้อมูลไม่ครบ"}


def test_search_muteteam_returns_list_of_matches(client):
    cache = {"muteteam": {"150ab01": "150AB01.jpg", "150ab02": "150AB02.jpg"}}
    with mock.patch.object(system_blueprint, "CACHED_FILES", cache), \
         mock.patch.object(system_blueprint, "is_loaded", return_value=True):
        resp = client.get("/api/search", query_string={"page": "muteteam", "code": "150ab"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["found"] is True
    assert body["count"] == 2
    assert {r["code"] for r in body["results"]} == {"150AB01", "150AB02"}


def test_search_muteteam_404_when_no_match(client):
    with mock.patch.object(system_blueprint, "CACHED_FILES", {"muteteam": {}}), \
         mock.patch.object(system_blueprint, "is_loaded", return_value=True):
        resp = client.get("/api/search", query_string={"page": "muteteam", "code": "nope"})

    assert resp.status_code == 404
    assert resp.get_json() == {"found": False, "message": "ไม่พบรูปภาพ"}


def test_search_mahabucha_returns_single_match(client):
    cache = {"mahabucha": {"150ab01": "150AB01.jpg"}}
    with mock.patch.object(system_blueprint, "CACHED_FILES", cache), \
         mock.patch.object(system_blueprint, "is_loaded", return_value=True):
        resp = client.get("/api/search", query_string={"page": "mahabucha", "code": "150ab01"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {
        "found": True,
        "code": "150AB01",
        "image_url": system_blueprint.get_image_url("mahabucha", "150AB01.jpg"),
    }


def test_search_mahabucha_404_when_no_exact_match(client):
    with mock.patch.object(system_blueprint, "CACHED_FILES", {"mahabucha": {}}), \
         mock.patch.object(system_blueprint, "is_loaded", return_value=True):
        resp = client.get("/api/search", query_string={"page": "mahabucha", "code": "nope"})

    assert resp.status_code == 404
    assert resp.get_json() == {"found": False, "message": "ไม่พบรูปภาพ"}
