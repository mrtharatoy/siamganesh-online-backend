"""
Characterization tests for:
  GET  /api/line-quota     (the ACTIVE handler -- see API_BASELINE.md
                             #12 vs #15; the dead-code duplicate handler
                             was dropped when moving to
                             core/blueprints/notifications.py, SG-B-104)
  POST /api/line-webhook

send_line_notification() lives in core/clients/line_client.py
(SG-B-104), so LINE_CHANNEL_ACCESS_TOKEN/LINE_GROUP_ID must be patched
there -- that's the module those functions' own global lookups
resolve against.

`/api/notify-photo` was removed in the SG-B-2xx LINE consolidation
(print-queue notifications are now a once-daily digest, not an
instant per-booking push) -- see tests/test_notification_service.py
and app.py's print-queue digest tests for its replacement.
"""
from unittest import mock

import pytest

import core.clients.line_client as line_client


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


# --- GET /api/line-quota ---


def test_line_quota_returns_null_when_token_unset(client):
    # LINE_CHANNEL_ACCESS_TOKEN is unset in the test env, so
    # fetch_quota's `if not token: return None` guard fires without any
    # network call.
    resp = client.get("/api/line-quota")
    assert resp.status_code == 200
    assert resp.get_json() == {"quota": None}


def test_line_quota_calls_line_api_when_token_present(client):
    fake_usage_response = mock.Mock(status_code=200)
    fake_usage_response.json.return_value = {"totalUsage": 42}
    fake_limit_response = mock.Mock(status_code=200)
    fake_limit_response.json.return_value = {"value": 1000}

    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", "shared-token"), \
         mock.patch("requests.get", side_effect=[fake_usage_response, fake_limit_response]):
        resp = client.get("/api/line-quota")

    assert resp.status_code == 200
    assert resp.get_json() == {"quota": {"usage": 42, "limit": 1000}}


# --- POST /api/line-webhook ---


def test_line_webhook_returns_ok_for_any_json_body(client):
    resp = client.post("/api/line-webhook", json={"events": []})
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "OK"


def test_line_webhook_returns_error_500_when_body_is_not_valid_json(client):
    resp = client.post(
        "/api/line-webhook", data="not-json-at-all", content_type="application/json"
    )
    assert resp.status_code == 500
    assert resp.get_data(as_text=True) == "Error"
