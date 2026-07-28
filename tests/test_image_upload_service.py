"""
Direct unit tests for core/services/image_upload_service.py (SG-B-202).
Route-level behavior is already covered end-to-end in
tests/test_route_images.py; these tests exercise the service functions
directly, independent of Flask.
"""
from unittest import mock

import core.services.image_upload_service as service


def test_upload_images_for_booking_mahabucha_never_calls_github():
    with mock.patch.object(service, "get_file_sha") as mock_sha, \
         mock.patch.object(service, "put_file") as mock_put, \
         mock.patch.object(service, "update_file_list"):
        result = service.upload_images_for_booking(
            "150AA010001", [{"index": 1, "ext": "webp", "data": "ZmFrZQ=="}], "mahabucha",
        )

    assert result["success"] is True
    assert result["uploaded"] == ["150AA010001_1.webp"]
    mock_sha.assert_not_called()
    mock_put.assert_not_called()


def test_upload_images_for_booking_muteteam_skips_when_no_token():
    with mock.patch.object(service, "GITHUB_TOKEN", None), \
         mock.patch.object(service, "get_file_sha") as mock_sha:
        result = service.upload_images_for_booking(
            "150AA010001", [{"index": 1, "ext": "webp", "data": "ZmFrZQ=="}], "muteteam",
        )

    assert result["success"] is False
    assert result["uploaded"] == []
    mock_sha.assert_not_called()


def test_upload_images_for_booking_muteteam_uploads_via_github_when_token_present():
    with mock.patch.object(service, "GITHUB_TOKEN", "fake-token"), \
         mock.patch.object(service, "get_file_sha", return_value=None), \
         mock.patch.object(service, "put_file", return_value=(True, None)), \
         mock.patch.object(service, "update_file_list") as mock_refresh:
        result = service.upload_images_for_booking(
            "150AA010001", [{"index": 1, "ext": "webp", "data": "ZmFrZQ=="}], "muteteam",
        )

    assert result["success"] is True
    assert result["uploaded"] == ["150AA010001_1.webp"]


def test_upload_images_for_booking_skips_images_with_no_data():
    with mock.patch.object(service, "put_file") as mock_put:
        result = service.upload_images_for_booking(
            "150AA010001", [{"index": 1, "ext": "webp", "data": ""}], "mahabucha",
        )
    # No data -> the image is skipped entirely, so it's never even counted uploaded.
    assert result["uploaded"] == []
    assert result["success"] is False
    mock_put.assert_not_called()


def test_upload_raw_images_success():
    with mock.patch.object(service, "GITHUB_TOKEN", "fake-token"), \
         mock.patch.object(service, "get_file_sha", return_value="existing-sha"), \
         mock.patch.object(service, "put_file", return_value=(True, None)) as mock_put, \
         mock.patch.object(service, "update_file_list"):
        result = service.upload_raw_images("muteteam", [{"filename": "a.jpg", "data": "ZmFrZQ=="}])

    assert result["success"] is True
    assert result["uploaded"] == ["a.jpg"]
    mock_put.assert_called_once_with("images/muteteam/a.jpg", "ZmFrZQ==", "Upload raw photo: a.jpg", branch=mock.ANY, sha="existing-sha")


def test_upload_raw_images_records_error_message_on_failure():
    with mock.patch.object(service, "get_file_sha", return_value=None), \
         mock.patch.object(service, "put_file", return_value=(False, "Validation Failed")):
        result = service.upload_raw_images("muteteam", [{"filename": "a.jpg", "data": "ZmFrZQ=="}])

    assert result["success"] is False
    assert result["errors"] == ["GitHub a.jpg: Validation Failed"]


def test_delete_image_file_not_found():
    with mock.patch.object(service, "get_file_sha_at_ref", return_value=(None, 404)):
        result = service.delete_image_file("muteteam", "a.jpg")

    assert result == {"success": False, "message": "ไม่พบไฟล์ใน GitHub หรือข้ามไป (404)"}


def test_delete_image_file_success():
    with mock.patch.object(service, "get_file_sha_at_ref", return_value=("abc123", 200)), \
         mock.patch.object(service, "delete_file", return_value=(True, None)), \
         mock.patch.object(service, "update_file_list"):
        result = service.delete_image_file("muteteam", "a.jpg")

    assert result == {"success": True, "message": "ลบไฟล์ออกจาก GitHub สำเร็จ"}


def test_delete_image_file_failure_includes_github_error():
    with mock.patch.object(service, "get_file_sha_at_ref", return_value=("abc123", 200)), \
         mock.patch.object(service, "delete_file", return_value=(False, "some error")):
        result = service.delete_image_file("muteteam", "a.jpg")

    assert result == {"success": False, "message": "ลบไฟล์จาก GitHub ไม่สำเร็จ: some error"}
