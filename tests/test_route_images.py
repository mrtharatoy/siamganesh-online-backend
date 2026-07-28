"""
Characterization tests for the image upload/delete routes:
  POST /api/upload-image
  POST /api/upload-github-raw
  POST /api/delete-image

These routes call the real GitHub Contents API via `requests`. Every
test here mocks `requests.get/put/delete` explicitly rather than
relying on any live network access, per conftest.py's "no real network
in tests" policy. GITHUB_TOKEN is unset in the test environment
(conftest.py does not set it), so tests that need a token present
patch it on core.blueprints.images (SG-B-103 -- where these routes now
live and look the name up from), not on the app module.
"""
from unittest import mock

import pytest

import core.blueprints.images as images_blueprint


@pytest.fixture
def client(app_module):
    app_module.app.testing = True
    return app_module.app.test_client()


# --- POST /api/upload-image ---


def test_upload_image_400_when_body_missing(client):
    resp = client.post("/api/upload-image", data="not json", content_type="text/plain")
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_upload_image_400_when_required_fields_missing(client):
    resp = client.post("/api/upload-image", json={"owner": "muteteam"})
    assert resp.status_code == 400
    assert resp.get_json() == {"success": False, "message": "ข้อมูลไม่ครบ"}


def test_upload_image_mahabucha_owner_always_counts_as_uploaded_without_github_call(client):
    # Documented quirk (API_BASELINE.md #7): owner != "muteteam" never
    # calls GitHub at all, but is still reported as a successful upload.
    # "uploaded" is still non-empty here, so the route spawns a
    # background thread calling update_file_list() -- patch it out so
    # that stray thread can't make a real GitHub API call and mutate
    # global CACHED_FILES/TOTAL_IMAGES_SIZE state for other tests.
    with mock.patch("requests.get") as mock_get, mock.patch("requests.put") as mock_put, \
         mock.patch.object(images_blueprint, "update_file_list"):
        resp = client.post(
            "/api/upload-image",
            json={
                "booking_code": "150AA010001",
                "owner": "mahabucha",
                "images": [{"index": 1, "ext": "webp", "data": "ZmFrZQ=="}],
            },
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["uploaded"] == ["150AA010001_1.webp"]
    assert body["errors"] == []
    mock_get.assert_not_called()
    mock_put.assert_not_called()


def test_upload_image_muteteam_owner_without_github_token_uploads_nothing(client):
    # GITHUB_TOKEN is unset in the test env, so the "Skipped GitHub
    # upload (No Token)" branch is taken and nothing succeeds -> 500.
    assert images_blueprint.GITHUB_TOKEN in (None, "")
    resp = client.post(
        "/api/upload-image",
        json={
            "booking_code": "150AA010001",
            "owner": "muteteam",
            "images": [{"index": 1, "ext": "webp", "data": "ZmFrZQ=="}],
        },
    )
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False
    assert body["uploaded"] == []


def test_upload_image_muteteam_owner_with_token_uploads_via_github(client):
    fake_get_response = mock.Mock(status_code=404)  # no existing file -> no sha
    fake_put_response = mock.Mock(status_code=201)

    with mock.patch.object(images_blueprint, "GITHUB_TOKEN", "fake-token"), mock.patch(
        "requests.get", return_value=fake_get_response
    ) as mock_get, mock.patch(
        "requests.put", return_value=fake_put_response
    ) as mock_put, mock.patch.object(
        images_blueprint, "update_file_list"
    ):
        resp = client.post(
            "/api/upload-image",
            json={
                "booking_code": "150AA010001",
                "owner": "muteteam",
                "images": [{"index": 1, "ext": "webp", "data": "ZmFrZQ=="}],
            },
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["uploaded"] == ["150AA010001_1.webp"]
    mock_get.assert_called_once()
    mock_put.assert_called_once()


# --- POST /api/upload-github-raw ---


def test_upload_github_raw_400_when_fields_missing(client):
    resp = client.post("/api/upload-github-raw", json={"owner": "muteteam", "images": []})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_upload_github_raw_500_when_no_github_token(client):
    assert images_blueprint.GITHUB_TOKEN in (None, "")
    resp = client.post(
        "/api/upload-github-raw",
        json={"owner": "muteteam", "images": [{"filename": "a.jpg", "data": "ZmFrZQ=="}]},
    )
    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "message": "ไม่มี GITHUB_TOKEN"}


def test_upload_github_raw_success_with_token(client):
    fake_get_response = mock.Mock(status_code=404)
    fake_put_response = mock.Mock(status_code=201)

    with mock.patch.object(images_blueprint, "GITHUB_TOKEN", "fake-token"), mock.patch(
        "requests.get", return_value=fake_get_response
    ), mock.patch("requests.put", return_value=fake_put_response), mock.patch.object(
        images_blueprint, "update_file_list"
    ):
        resp = client.post(
            "/api/upload-github-raw",
            json={"owner": "muteteam", "images": [{"filename": "a.jpg", "data": "ZmFrZQ=="}]},
        )

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["success"] is True
    assert body["uploaded"] == ["a.jpg"]


# --- POST /api/delete-image ---


def test_delete_image_500_when_no_github_token(client):
    assert images_blueprint.GITHUB_TOKEN in (None, "")
    resp = client.post("/api/delete-image", json={"page": "muteteam", "filename": "a.jpg"})
    assert resp.status_code == 500
    assert resp.get_json() == {"success": False, "message": "ไม่มี GITHUB_TOKEN"}


def test_delete_image_400_when_page_invalid_or_filename_missing(client):
    with mock.patch.object(images_blueprint, "GITHUB_TOKEN", "fake-token"):
        resp = client.post("/api/delete-image", json={"page": "not-a-real-page", "filename": "a.jpg"})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False


def test_delete_image_success_when_file_exists(client):
    fake_get_response = mock.Mock(status_code=200)
    fake_get_response.json.return_value = {"sha": "abc123"}
    fake_delete_response = mock.Mock(status_code=200)

    with mock.patch.object(images_blueprint, "GITHUB_TOKEN", "fake-token"), mock.patch(
        "requests.get", return_value=fake_get_response
    ), mock.patch("requests.delete", return_value=fake_delete_response), mock.patch.object(
        images_blueprint, "update_file_list"
    ):
        resp = client.post("/api/delete-image", json={"page": "muteteam", "filename": "a.jpg"})

    assert resp.status_code == 200
    assert resp.get_json() == {"success": True, "message": "ลบไฟล์ออกจาก GitHub สำเร็จ"}


def test_delete_image_500_when_file_not_found_on_github(client):
    fake_get_response = mock.Mock(status_code=404)

    with mock.patch.object(images_blueprint, "GITHUB_TOKEN", "fake-token"), mock.patch(
        "requests.get", return_value=fake_get_response
    ):
        resp = client.post("/api/delete-image", json={"page": "muteteam", "filename": "a.jpg"})

    assert resp.status_code == 500
    assert resp.get_json()["success"] is False
