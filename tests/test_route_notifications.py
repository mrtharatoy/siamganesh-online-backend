"""
Characterization tests for:
  GET  /api/line-quota     (the ACTIVE handler at app.py line ~983 --
                             see API_BASELINE.md #12 vs #15)
  POST /api/line-webhook
  POST /api/notify-photo

LINE_CHANNEL_ACCESS_TOKEN* and LINE_GROUP_ID_* are unset in the test
environment, so send_line_notification()'s "missing token/group"
guards are exercised by default without needing to mock anything. A
success path is added for notify-photo by patching the relevant
app_module constants and `requests.post`.
"""
from unittest import mock

import pytest


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


# --- GET /api/line-quota ---


def test_line_quota_returns_null_for_both_owners_when_tokens_unset(app_module, client):
    # LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA/MUTETEAM are unset in the test
    # env, so get_line_token() falls back to the base
    # LINE_CHANNEL_ACCESS_TOKEN, also unset -> fetch_quota's `if not
    # token: return None` guard fires for both owners without any
    # network call.
    resp = client.get("/api/line-quota")
    assert resp.status_code == 200
    assert resp.get_json() == {"muteteam": None, "mahabucha": None}


def test_line_quota_calls_line_api_when_token_present(app_module, client):
    fake_usage_response = mock.Mock(status_code=200)
    fake_usage_response.json.return_value = {"totalUsage": 42}
    fake_limit_response = mock.Mock(status_code=200)
    fake_limit_response.json.return_value = {"value": 1000}

    with mock.patch.object(app_module, "LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM", "muteteam-token"), \
         mock.patch.object(app_module, "LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA", None), \
         mock.patch.object(app_module, "LINE_CHANNEL_ACCESS_TOKEN", None), \
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


def test_notify_photo_returns_200_with_success_false_when_line_send_fails(app_module, client):
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


def test_notify_photo_success_path_sends_line_notification(app_module, client):
    fake_response = mock.Mock(status_code=200)

    with mock.patch.object(app_module, "LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA", "fake-token"), \
         mock.patch.object(app_module, "LINE_GROUP_ID_MAHABUCHA", "fake-group"), \
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
