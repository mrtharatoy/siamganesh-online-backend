"""
Characterization tests for the AI blueprint routes (SG-B-105):
  GET /api/generate-message

No test previously existed for this route. get_booking_names is
patched on core.blueprints.ai (where the route lives and looks the
name up from), not on the app module.
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
    # SUPABASE_URL/KEY are empty in the test env, so get_booking_names()
    # takes its deterministic no-network fallback path; the message is
    # always the static template now that the Gemini branch is removed.
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
