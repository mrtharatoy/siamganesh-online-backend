"""
Characterization tests for:
  GET  /api/line-quota     (the ACTIVE handler -- see API_BASELINE.md
                             #12 vs #15; the dead-code duplicate handler
                             was dropped when moving to
                             core/blueprints/notifications.py, SG-B-104)
  POST /api/line-webhook
  POST /api/notify-photo

get_line_token()/send_line_notification() moved to
core/clients/line_client.py (SG-B-104), so LINE_CHANNEL_ACCESS_TOKEN*/
LINE_GROUP_ID_* must be patched there -- that's the module those
functions' own global lookups resolve against, not the app module
(which only re-exports send_line_notification for the scheduler
functions, not get_line_token or the LINE config constants at all
anymore).
"""
from unittest import mock

import pytest

import core.clients.line_client as line_client


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


# --- GET /api/line-quota ---


def test_line_quota_returns_null_for_both_owners_when_tokens_unset(client):
    # LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA/MUTETEAM are unset in the test
    # env, so get_line_token() falls back to the base
    # LINE_CHANNEL_ACCESS_TOKEN, also unset -> fetch_quota's `if not
    # token: return None` guard fires for both owners without any
    # network call.
    resp = client.get("/api/line-quota")
    assert resp.status_code == 200
    assert resp.get_json() == {"muteteam": None, "mahabucha": None}


def test_line_quota_calls_line_api_when_token_present(client):
    fake_usage_response = mock.Mock(status_code=200)
    fake_usage_response.json.return_value = {"totalUsage": 42}
    fake_limit_response = mock.Mock(status_code=200)
    fake_limit_response.json.return_value = {"value": 1000}

    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM", "muteteam-token"), \
         mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA", None), \
         mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", None), \
         mock.patch("requests.get", side_effect=[fake_usage_response, fake_limit_response]):
        resp = client.get("/api/line-quota")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["muteteam"] == {"usage": 42, "limit": 1000}
    assert body["mahabucha"] is None


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


# --- POST /api/notify-photo ---


def test_notify_photo_400_when_owner_or_booking_code_missing(client):
    resp = client.post("/api/notify-photo", json={"owner": "mahabucha"})
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "message": "ข้อมูลไม่ครบถ้วน"}


def test_notify_photo_returns_200_with_success_false_when_line_send_fails(client):
    # Documented quirk (API_BASELINE.md #14): a LINE send failure still
    # returns HTTP 200, just with success=False in the body. Tokens are
    # unset in the test env so this is the default path.
    resp = client.post(
        "/api/notify-photo",
        json={"owner": "mahabucha", "booking_code": "150AA010001", "person1_name": "สมชาย"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is False
    assert "error" in body


def test_notify_photo_success_path_sends_line_notification(client):
    fake_response = mock.Mock(status_code=200)

    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA", "fake-token"), \
         mock.patch.object(line_client, "LINE_GROUP_ID_MAHABUCHA", "fake-group"), \
         mock.patch("requests.post", return_value=fake_response) as mock_post:
        resp = client.post(
            "/api/notify-photo",
            json={"owner": "mahabucha", "booking_code": "150AA010001", "person1_name": "สมชาย"},
        )

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}
    mock_post.assert_called_once()
    sent_text = mock_post.call_args.kwargs["json"]["messages"][0]["text"]
    assert "150AA010001" in sent_text
    assert "สมชาย" in sent_text
