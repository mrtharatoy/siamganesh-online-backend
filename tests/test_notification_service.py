"""
Tests for core/services/notification_service.py (SG-B-202 original;
SG-B-2xx rewrote print-queue notifications from an instant per-booking
push to a once-daily digest per owner). Route-level scheduling lives
in app.py's *_print_queue_digest jobs; these exercise message
composition and the send wrapper directly.
"""
from unittest import mock

import core.services.notification_service as service


def test_booking_display_name_uses_both_names_when_both_present():
    assert service.booking_display_name(person1_name="สมชาย", person2_name="สมหญิง") == "สมชาย และ สมหญิง"


def test_booking_display_name_falls_back_to_customer_name_when_no_person_names():
    assert service.booking_display_name(customer_name="ลูกค้าทั่วไป") == "ลูกค้าทั่วไป"


def test_booking_display_name_uses_unspecified_label_when_no_names_at_all():
    assert service.booking_display_name() == "ไม่ระบุชื่อ"


def test_send_print_queue_digest_is_a_noop_for_empty_items():
    with mock.patch.object(service, "send_line_notification") as mock_send:
        success, err = service.send_print_queue_digest("muteteam", [])
    assert success is True
    assert err is None
    mock_send.assert_not_called()


def test_send_print_queue_digest_includes_tray_count_for_muteteam_only():
    items = [{"booking_code": "150AA010001", "display_name": "สมชาย", "tray_count": 3}]

    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.send_print_queue_digest("muteteam", items)
    assert "3 องค์เทพ" in mock_send.call_args.args[1]

    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.send_print_queue_digest("mahabucha", items)
    assert "องค์เทพ" not in mock_send.call_args.args[1]


def test_send_print_queue_digest_lists_every_item_and_uses_page_display_name():
    items = [
        {"booking_code": "150AA010001", "display_name": "สมชาย", "tray_count": 1},
        {"booking_code": "150AA010002", "display_name": "สมหญิง", "tray_count": 1},
    ]

    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.send_print_queue_digest("laos", items)

    text = mock_send.call_args.args[1]
    assert "เพจ: สยามคเณศ (ลาว)" in text
    assert "150AA010001" in text
    assert "150AA010002" in text
    assert "จำนวนรายการวันนี้: 2 รายการ" in text


def test_send_print_queue_digest_returns_send_line_notification_result():
    with mock.patch.object(service, "send_line_notification", return_value=(False, "some error")):
        success, err = service.send_print_queue_digest(
            "muteteam", [{"booking_code": "150AA010001", "display_name": "สมชาย", "tray_count": 1}]
        )
    assert success is False
    assert err == "some error"
