"""
Tests for core/errors.py (SG-B-107).

Before this module existed, an unmatched route or an unhandled
exception fell through to Flask's default HTML error pages (verified
directly against a running instance beforehand -- see core/errors.py's
docstring). This is a deliberate, approved behavior change: these two
cases now return JSON instead. Every route's own explicit error
responses (400s, route-specific 500s, etc.) are untouched -- Flask
only invokes these handlers for an unmatched route or a genuinely
unhandled exception, never for a route's own early `return`.
"""
import pytest

import app as app_module_for_route_setup

# Flask refuses new route registration after the app has served its
# first request, and app_module is a session-scoped singleton other
# test modules already send requests through -- so this throwaway
# route (used only to trigger a genuinely unhandled exception) must be
# registered at collection time, before any test anywhere has run,
# rather than inside a test function.
@app_module_for_route_setup.app.route("/__test_only_boom")
def _boom():
    raise RuntimeError("kaboom")


@pytest.fixture
def client(app_module):
    # PROPAGATE_EXCEPTIONS defaults to None, which behaves like False
    # when TESTING/DEBUG are off -- set testing explicitly False so an
    # unhandled exception in the test below goes through the real
    # errorhandler machinery instead of propagating to the test itself,
    # matching how a production WSGI server actually behaves.
    app_module.app.testing = False
    return app_module.app.test_client()


def test_unmatched_route_returns_json_404(client):
    resp = client.get("/api/this-route-does-not-exist")
    assert resp.status_code == 404
    assert resp.content_type == "application/json"
    assert resp.get_json() == {"error": "not found"}


def test_unhandled_exception_returns_json_500(client):
    resp = client.get("/__test_only_boom")
    assert resp.status_code == 500
    assert resp.content_type == "application/json"
    assert resp.get_json() == {"error": "internal server error"}


def test_route_specific_error_responses_are_unaffected(client):
    # A route's own explicit early-return error response must pass
    # through completely unchanged -- the generic handlers only apply
    # to unmatched routes / truly unhandled exceptions.
    resp = client.get("/api/search")
    assert resp.status_code == 400
    assert resp.get_json() == {"found": False, "message": "ข้อมูลไม่ครบ"}
