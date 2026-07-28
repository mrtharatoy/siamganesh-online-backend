"""
Tests for core/clients/gemini_client.py (SG-B-201).
"""
from unittest import mock

import core.clients.gemini_client as gemini_client


def test_generate_content_builds_v1_url_and_returns_response():
    fake = mock.Mock(status_code=200)
    with mock.patch("requests.post", return_value=fake) as mock_post:
        result = gemini_client.generate_content("gemini-1.5-flash", {"contents": []}, api_version="v1", timeout=15)

    assert result is fake
    called_url = mock_post.call_args.args[0]
    assert called_url.startswith("https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=")
    assert mock_post.call_args.kwargs["json"] == {"contents": []}
    assert mock_post.call_args.kwargs["timeout"] == 15
    assert "headers" not in mock_post.call_args.kwargs


def test_generate_content_builds_v1beta_url_for_different_model():
    fake = mock.Mock(status_code=200)
    with mock.patch("requests.post", return_value=fake) as mock_post:
        gemini_client.generate_content("gemini-2.5-flash-lite", {}, api_version="v1beta", timeout=20)

    called_url = mock_post.call_args.args[0]
    assert "/v1beta/models/gemini-2.5-flash-lite:generateContent" in called_url


def test_generate_content_passes_custom_headers_when_given():
    fake = mock.Mock(status_code=200)
    with mock.patch("requests.post", return_value=fake) as mock_post:
        gemini_client.generate_content(
            "gemini-1.5-flash", {}, api_version="v1beta", timeout=30,
            headers={"Content-Type": "application/json"},
        )

    assert mock_post.call_args.kwargs["headers"] == {"Content-Type": "application/json"}
