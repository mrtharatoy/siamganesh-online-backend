"""
Characterization tests for the messenger blueprint routes (SG-B-102):
  GET  /              (Facebook webhook verify handshake)
  POST /              (Facebook webhook receiver)
  GET  /api/debug-webhook
  POST /api/send-fb-message-manual

Incoming customer messages must not invoke any automatic reply. The manual
send route is covered separately and remains available to authenticated admins.
"""
from unittest import mock

import pytest

import core.blueprints.messenger as messenger_blueprint


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


# --- GET / (verify) ---


def test_verify_returns_challenge_when_token_matches(app_module, client):
    resp = client.get("/", query_string={"hub.verify_token": "test-verify-token", "hub.challenge": "12345"})
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "12345"


def test_verify_returns_live_message_when_token_does_not_match(client):
    resp = client.get("/", query_string={"hub.verify_token": "wrong-token", "hub.challenge": "12345"})
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "[OK] Siamganesh Online Backend is Live"


# --- POST / (webhook) ---


def test_webhook_returns_ok_for_non_page_object(client):
    resp = client.post("/", json={"object": "not-page"})
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "ok"


def test_webhook_accepts_customer_text_without_sending_an_automatic_reply(client):
    payload = {
        "object": "page",
        "entry": [{
            "id": "123",
            "messaging": [{
                "sender": {"id": "user1"},
                "recipient": {"id": "page1"},
                "message": {"text": "150ab01"},
            }],
        }],
    }
    with mock.patch.object(messenger_blueprint, "send_fb_action") as mock_send:
        resp = client.post("/", json=payload)

    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "ok"
    mock_send.assert_not_called()


def test_webhook_accepts_bot_sent_echo_messages_without_responding(client):
    payload = {
        "object": "page",
        "entry": [{
            "id": "123",
            "messaging": [{
                "sender": {"id": "user1"},
                "recipient": {"id": "page1"},
                "message": {"text": "hello", "is_echo": True, "metadata": "BOT_SENT_THIS"},
            }],
        }],
    }
    with mock.patch.object(messenger_blueprint, "send_fb_action") as mock_send:
        resp = client.post("/", json=payload)
    assert resp.status_code == 200
    mock_send.assert_not_called()


# --- GET /api/debug-webhook ---


def test_debug_webhook_returns_no_credentials_error_when_supabase_not_configured(client):
    resp = client.get("/api/debug-webhook")
    assert resp.get_json() == {"error": "no credentials"}


def test_debug_webhook_returns_supabase_rows_when_configured(app_module, client):
    fake_response = mock.Mock()
    fake_response.json.return_value = [{"id": "debug_webhook", "value": {"event": "x"}}]

    with mock.patch.object(messenger_blueprint, "SUPABASE_URL", "https://example.supabase.co"), \
         mock.patch.object(messenger_blueprint, "SUPABASE_KEY", "fake-key"), \
         mock.patch("core.clients.supabase_rest_client.requests.get", return_value=fake_response):
        resp = client.get("/api/debug-webhook")

    assert resp.status_code == 200
    assert resp.get_json() == [{"id": "debug_webhook", "value": {"event": "x"}}]


# --- POST /api/send-fb-message-manual ---


def test_send_fb_message_manual_400_when_owner_or_psid_missing(client):
    resp = client.post("/api/send-fb-message-manual", json={"owner": "mahabucha"})
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "error": "Missing owner or psid"}


def test_send_fb_message_manual_sends_text_and_images_on_success(client):
    with mock.patch.object(messenger_blueprint, "send_fb_action", return_value=(True, "")) as mock_send:
        resp = client.post(
            "/api/send-fb-message-manual",
            json={"owner": "mahabucha", "psid": "user1", "message": "hi", "images": ["https://x/1.jpg"]},
        )

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True}
    sent = [(call.args[2], call.args[3]) for call in mock_send.call_args_list]
    assert ("text", "hi") in sent
    assert ("image", "https://x/1.jpg") in sent


def test_send_fb_message_manual_500_when_an_image_send_fails(client):
    with mock.patch.object(
        messenger_blueprint, "send_fb_action", side_effect=[(False, "FB Error 400: bad url")]
    ):
        resp = client.post(
            "/api/send-fb-message-manual",
            json={"owner": "muteteam", "psid": "user1", "images": ["https://x/1.jpg"]},
        )

    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "error": "FB Error 400: bad url"}
