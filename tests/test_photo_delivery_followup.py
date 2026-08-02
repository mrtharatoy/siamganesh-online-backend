"""Coverage for the 21:00 post-ceremony photo-delivery follow-up."""
from unittest import mock

import pytest


@pytest.fixture
def supabase_configured(app_module):
    with mock.patch.object(app_module, "SUPABASE_URL", "https://example.supabase.co"), \
         mock.patch.object(app_module, "SUPABASE_KEY", "fake-key"):
        yield


def _response(value):
    return mock.Mock(status_code=200, json=lambda: value)


def test_photo_followup_reports_only_customers_pending_after_a_ceremony(app_module, supabase_configured):
    with mock.patch(
        "requests.get",
        side_effect=[
            _response([{ "value": {"mahabucha": True} }]),
            _response([{ "id": "event-1", "caption": "งานมหาบูชา", "event_date": "2026-08-01" }]),
            _response([{ "gallery_id": "event-1" }, { "gallery_id": "event-1" }]),
            _response([]),
        ],
    ), mock.patch("requests.post", return_value=mock.Mock(status_code=201)) as mock_post, \
         mock.patch.object(app_module, "send_line_notification", return_value=(True, None)) as mock_send:
        app_module._owner_photo_delivery_followup("mahabucha")

    text = mock_send.call_args.args[1]
    assert "📦 [ติดตามคิวรอส่งภาพ]" in text
    assert "เพจ: มหาบูชา" in text
    assert "งานมหาบูชา (จัดพิธี 1 ส.ค. 2569): 2 คน" in text
    assert "รวมค้างส่งภาพ 2 คน" in text
    saved_state = mock_post.call_args.kwargs["json"]["value"]["mahabucha"]
    assert saved_state == {"tracked_gallery_ids": ["event-1"], "completed_gallery_ids": []}


def test_photo_followup_sends_a_single_completion_for_a_tracked_empty_queue(app_module, supabase_configured):
    current_state = {
        "mahabucha": {"tracked_gallery_ids": ["event-1"], "completed_gallery_ids": []},
    }
    with mock.patch(
        "requests.get",
        side_effect=[
            _response([{ "value": {"mahabucha": True} }]),
            _response([{ "id": "event-1", "caption": "งานมหาบูชา", "event_date": "2026-08-01" }]),
            _response([]),
            _response([{ "value": current_state }]),
        ],
    ), mock.patch("requests.post", return_value=mock.Mock(status_code=201)) as mock_post, \
         mock.patch.object(app_module, "send_line_notification", return_value=(True, None)) as mock_send:
        app_module._owner_photo_delivery_followup("mahabucha")

    text = mock_send.call_args.args[1]
    assert "✅ [ปิดคิวส่งภาพ]" in text
    assert "สถานะ: ส่งภาพให้ลูกค้าครบแล้ว" in text
    saved_state = mock_post.call_args.kwargs["json"]["value"]["mahabucha"]
    assert saved_state == {"tracked_gallery_ids": ["event-1"], "completed_gallery_ids": ["event-1"]}


def test_photo_followup_does_not_close_old_untracked_ceremonies(app_module, supabase_configured):
    with mock.patch(
        "requests.get",
        side_effect=[
            _response([{ "value": {"mahabucha": True} }]),
            _response([{ "id": "event-1", "caption": "งานมหาบูชา", "event_date": "2026-08-01" }]),
            _response([]),
            _response([]),
        ],
    ), mock.patch.object(app_module, "send_line_notification") as mock_send:
        app_module._owner_photo_delivery_followup("mahabucha")

    mock_send.assert_not_called()

