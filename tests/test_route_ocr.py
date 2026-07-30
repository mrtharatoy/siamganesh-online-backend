"""
Characterization tests for POST /api/ocr-image.

GEMINI_API_KEY is an empty string in the test environment
(conftest.py), which is falsy in Python, so the "not configured" 500
guard fires without any network call for the default case. This route
moved to core/blueprints/ai.py (SG-B-105), so success/NOT_FOUND/error
paths patch GEMINI_API_KEY there -- that's the module ocr_image()
actually looks the name up from now -- and `requests.post` directly,
the same pattern used elsewhere in this suite (see
test_ceremony_flow.py).
"""
from unittest import mock

import pytest

import core.blueprints.ai as ai_blueprint


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


def test_ocr_image_500_when_gemini_not_configured(client):
    assert ai_blueprint.GEMINI_API_KEY == ""
    resp = client.post("/api/ocr-image", json={"image": "data:image/png;base64,ZmFrZQ=="})
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "GEMINI_API_KEY is not configured"}


def test_ocr_image_400_when_no_image_data(client):
    with mock.patch.object(ai_blueprint, "GEMINI_API_KEY", "fake-key"):
        resp = client.post("/api/ocr-image", json={})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "No image data provided"}


def test_ocr_image_extracts_code_from_data_url(client):
    fake_response = mock.Mock(status_code=200)
    fake_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "150AA010001"}]}}]
    }

    with mock.patch.object(ai_blueprint, "GEMINI_API_KEY", "fake-key"), mock.patch(
        "requests.post", return_value=fake_response
    ) as mock_post:
        resp = client.post(
            "/api/ocr-image", json={"image": "data:image/jpeg;base64,ZmFrZQ=="}
        )

    assert resp.status_code == 200
    assert resp.get_json() == {"code": "150AA010001"}
    sent_payload = mock_post.call_args.kwargs["json"]
    inline_data = sent_payload["contents"][0]["parts"][1]["inline_data"]
    assert inline_data["mime_type"] == "image/jpeg"
    assert inline_data["data"] == "ZmFrZQ=="  # base64 prefix stripped


def test_ocr_image_returns_not_found_code_when_no_candidates(client):
    fake_response = mock.Mock(status_code=200)
    fake_response.json.return_value = {"candidates": []}

    with mock.patch.object(ai_blueprint, "GEMINI_API_KEY", "fake-key"), mock.patch(
        "requests.post", return_value=fake_response
    ):
        resp = client.post("/api/ocr-image", json={"image": "ZmFrZQ=="})

    assert resp.status_code == 200
    assert resp.get_json() == {"code": "NOT_FOUND"}


def test_ocr_image_500_when_gemini_api_errors(client):
    fake_response = mock.Mock(status_code=503, text="service unavailable")

    with mock.patch.object(ai_blueprint, "GEMINI_API_KEY", "fake-key"), mock.patch(
        "requests.post", return_value=fake_response
    ):
        resp = client.post("/api/ocr-image", json={"image": "ZmFrZQ=="})

    assert resp.status_code == 500
    body = resp.get_json()
    assert "Gemini API returned 503" in body["error"]
