"""
SG-H-101: unit tests for core/schemas.py's own validation rules,
independent of the route-level tests (test_route_*.py) that already
lock in each endpoint's exact error response. These tests exist so a
schema regression is caught at the schema level, not only indirectly
through a route test.
"""
import pytest
from pydantic import ValidationError

from core.schemas import (
    DeleteImageBody,
    GenerateMessageQuery,
    ListImagesQuery,
    NotifyPhotoBody,
    OcrImageBody,
    SearchQuery,
    SendFbMessageManualBody,
    UploadGithubRawBody,
    UploadImageBody,
)


def test_search_query_lowercases_page_and_strips_code():
    q = SearchQuery(page="MUTETEAM", code="  ABC123  ")
    assert q.page == "muteteam"
    assert q.code == "abc123"


@pytest.mark.parametrize("page,code", [("not-a-page", "abc"), ("muteteam", ""), ("muteteam", "   ")])
def test_search_query_rejects_invalid_page_or_empty_code(page, code):
    with pytest.raises(ValidationError):
        SearchQuery(page=page, code=code)


def test_generate_message_query_strips_booking_code():
    assert GenerateMessageQuery(booking_code="  150AA010001  ").booking_code == "150AA010001"


def test_generate_message_query_rejects_blank_booking_code():
    with pytest.raises(ValidationError):
        GenerateMessageQuery(booking_code="   ")


def test_ocr_image_body_rejects_empty_image():
    with pytest.raises(ValidationError):
        OcrImageBody(image="")


def test_list_images_query_rejects_unknown_page():
    with pytest.raises(ValidationError):
        ListImagesQuery(page="unknown")


def test_upload_image_body_defaults_owner_to_muteteam():
    body = UploadImageBody(booking_code="150AA010001", images=[{"index": 1}])
    assert body.owner == "muteteam"


def test_upload_image_body_rejects_empty_images_list():
    with pytest.raises(ValidationError):
        UploadImageBody(booking_code="150AA010001", images=[])


def test_upload_github_raw_body_requires_owner_and_images():
    with pytest.raises(ValidationError):
        UploadGithubRawBody(owner="", images=[{"filename": "a.jpg"}])
    with pytest.raises(ValidationError):
        UploadGithubRawBody(owner="muteteam", images=[])


def test_delete_image_body_normalizes_page_case():
    body = DeleteImageBody(page="MAHABUCHA", filename="a.jpg")
    assert body.page == "mahabucha"


def test_send_fb_message_manual_body_defaults_images_to_empty_list():
    body = SendFbMessageManualBody(owner="mahabucha", psid="user1")
    assert body.images == []
    assert body.message is None


def test_send_fb_message_manual_body_rejects_missing_psid():
    with pytest.raises(ValidationError):
        SendFbMessageManualBody(owner="mahabucha", psid="")


def test_notify_photo_body_defaults_tray_count_to_zero():
    body = NotifyPhotoBody(owner="mahabucha", booking_code="150AA010001")
    assert body.tray_count == 0
    assert body.person1_name is None


def test_notify_photo_body_rejects_missing_booking_code():
    with pytest.raises(ValidationError):
        NotifyPhotoBody(owner="mahabucha", booking_code="")
