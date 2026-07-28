"""
Characterization tests for the AI blueprint routes (SG-B-105):
  GET /api/generate-message
  GET /api/debug-gemini

No test previously existed for either route. get_booking_names and
GEMINI_API_KEY are patched on core.blueprints.ai (where these routes
live and look the names up from), not on the app module.
"""
from unittest import mock

import pytest

import core.blueprints.ai as ai_blueprint


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


# --- GET /api/generate-message ---


def test_generate_message_400_when_booking_code_missing(client):
    resp = client.get("/api/generate-message")
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "message": "กรุณาระบุ booking_code"}


def test_generate_message_returns_fallback_message_with_booking_names(client):
    # SUPABASE_URL/KEY and GEMINI_API_KEY are empty in the test env, so
    # get_booking_names() and generate_thank_you_message() both take
    # their deterministic no-network fallback paths.
    resp = client.get("/api/generate-message", query_string={"booking_code": "150AA010001"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["booking_code"] == "150AA010001"
    assert body["person1_name"] is None
    assert body["person2_name"] is None
    assert "ขออนุญาตส่งมอบความสิริมงคล" in body["message"]


def test_generate_message_includes_booking_names_when_found(client):
    with mock.patch.object(ai_blueprint, "get_booking_names", return_value=("สมชาย", None)):
        resp = client.get("/api/generate-message", query_string={"booking_code": "150AA010001"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["person1_name"] == "สมชาย"
    assert "คุณสมชาย" in body["message"]


# --- GET /api/debug-gemini ---


def test_debug_gemini_500_when_gemini_not_configured(client):
    resp = client.get("/api/debug-gemini")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "GEMINI_API_KEY not set"}


def test_debug_gemini_returns_raw_response_when_configured(client):
    fake_response = mock.Mock(status_code=200)
    fake_response.headers = {"content-type": "application/json"}
    fake_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}

    with mock.patch.object(ai_blueprint, "GEMINI_API_KEY", "fake-key12345"), mock.patch(
        "requests.post", return_value=fake_response
    ):
        resp = client.get("/api/debug-gemini", query_string={"booking_code": "TEST001"})

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status_code"] == 200
    assert body["gemini_key_set"] is True
    assert body["key_prefix"] == "fake-key" + "..."
    assert body["raw_response"] == {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}
