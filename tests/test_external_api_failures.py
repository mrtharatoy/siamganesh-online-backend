"""
SG-005: integration tests for external-API failure/timeout paths that
weren't covered elsewhere. The existing route test files (test_route_*)
mostly characterize non-200 HTTP *status* responses from GitHub/LINE/
Facebook/Gemini; none of them exercise a genuinely *raised* exception
(timeout, connection error) from the underlying `requests` call, which
is the realistic failure mode in production when an external API is
unreachable.

Coverage added here, one client at a time:

- GitHub (core/clients/github_client.py): no try/except around any of
  its `requests.get/put/delete` calls, so a raised exception propagates
  all the way up through core/services/image_upload_service.py and the
  images blueprint uncaught. That's an existing, deliberate pattern
  (matches the original app.py code before SG-B-103/201) -- it's
  exercised here via the generic 500 JSON handler (core/errors.py,
  SG-B-107), the same way test_errors.py verifies unhandled exceptions
  elsewhere. Needs `app.testing = False` so Flask actually converts the
  exception instead of re-raising it into the test, matching
  test_errors.py's documented reasoning.
- Facebook (core/clients/facebook_client.py): same shape -- no
  try/except around `requests.post` in send_fb_action, so
  /api/send-fb-message-manual's uncaught exception also goes through
  the generic 500 handler.
- LINE (core/clients/line_client.py): the opposite shape --
  send_line_notification and fetch_quota both already wrap their
  requests calls in try/except and degrade gracefully (False/None)
  instead of raising. Covered here to lock in that resilience with a
  real exception, not just a non-200 status.
- Gemini (core/clients/gemini_client.py): generate_content itself has
  no try/except, but every caller (core/blueprints/ai.py's ocr_image
  and debug_gemini) wraps its call in its own try/except and returns a
  route-specific JSON 500 -- covered here with a real exception rather
  than the non-200-status case test_route_ocr.py already covers.
"""
from unittest import mock

import pytest
import requests

import core.blueprints.ai as ai_blueprint
import core.blueprints.images as images_blueprint
import core.blueprints.messenger as messenger_blueprint
import core.clients.line_client as line_client
import core.services.image_upload_service as image_upload_service


@pytest.fixture
def client(app_module):
    # See test_errors.py: PROPAGATE_EXCEPTIONS behaves like True when
    # app.testing is True, which would re-raise an unhandled exception
    # into the test itself instead of letting Flask's real errorhandler
    # machinery convert it to a 500 response. Off here because several
    # tests below rely on that conversion for routes with no
    # route-level try/except of their own.
    app_module.app.testing = False
    return app_module.app.test_client()


# --- GitHub timeout/connection failure (uncaught -> generic 500 JSON) ---


def test_upload_image_500_json_when_github_put_times_out(client):
    with mock.patch.object(image_upload_service, "GITHUB_TOKEN", "fake-token"), mock.patch(
        "requests.get", return_value=mock.Mock(status_code=404)
    ), mock.patch("requests.put", side_effect=requests.exceptions.Timeout("github timed out")):
        resp = client.post(
            "/api/upload-image",
            json={
                "booking_code": "150AA010001",
                "owner": "muteteam",
                "images": [{"index": 1, "ext": "webp", "data": "ZmFrZQ=="}],
            },
        )

    assert resp.status_code == 500
    assert resp.content_type == "application/json"
    assert resp.get_json() == {"error": "internal server error"}


def test_delete_image_500_json_when_github_get_connection_fails(client):
    with mock.patch.object(images_blueprint, "GITHUB_TOKEN", "fake-token"), mock.patch(
        "requests.get", side_effect=requests.exceptions.ConnectionError("no route to github")
    ):
        resp = client.post("/api/delete-image", json={"page": "muteteam", "filename": "a.jpg"})

    assert resp.status_code == 500
    assert resp.content_type == "application/json"
    assert resp.get_json() == {"error": "internal server error"}


# --- Facebook timeout (uncaught -> generic 500 JSON) ---


def test_send_fb_message_manual_500_json_when_facebook_api_times_out(client):
    with mock.patch("requests.post", side_effect=requests.exceptions.Timeout("fb timed out")):
        resp = client.post(
            "/api/send-fb-message-manual",
            json={"owner": "mahabucha", "psid": "user1", "message": "hi"},
        )

    assert resp.status_code == 500
    assert resp.content_type == "application/json"
    assert resp.get_json() == {"error": "internal server error"}


# --- LINE timeout (caught internally -> graceful degradation, not a 500) ---


def test_notify_photo_degrades_gracefully_when_line_send_times_out(client):
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA", "fake-token"), \
         mock.patch.object(line_client, "LINE_GROUP_ID_MAHABUCHA", "fake-group"), \
         mock.patch("requests.post", side_effect=requests.exceptions.Timeout("line timed out")):
        resp = client.post(
            "/api/notify-photo",
            json={"owner": "mahabucha", "booking_code": "150AA010001"},
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is False
    assert "line timed out" in body["error"]


def test_line_quota_returns_null_for_owner_when_line_api_times_out(client):
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM", "fake-token"), \
         mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", None), \
         mock.patch("requests.get", side_effect=requests.exceptions.Timeout("line timed out")):
        resp = client.get("/api/line-quota")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["muteteam"] is None


# --- Gemini timeout (caught by the route's own try/except -> route-specific 500 JSON) ---


def test_ocr_image_500_when_gemini_call_times_out(client):
    with mock.patch.object(ai_blueprint, "GEMINI_API_KEY", "fake-key"), mock.patch(
        "requests.post", side_effect=requests.exceptions.Timeout("gemini timed out")
    ):
        resp = client.post("/api/ocr-image", json={"image": "ZmFrZQ=="})

    assert resp.status_code == 500
    assert resp.get_json() == {"error": "gemini timed out"}


def test_debug_gemini_500_when_gemini_call_times_out(client):
    with mock.patch.object(ai_blueprint, "GEMINI_API_KEY", "fake-key"), mock.patch(
        "requests.post", side_effect=requests.exceptions.Timeout("gemini timed out")
    ):
        resp = client.get("/api/debug-gemini")

    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error"] == "gemini timed out"
    assert body["gemini_key_set"] is True
