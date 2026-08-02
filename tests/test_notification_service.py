"""
Tests for core/services/notification_service.py (SG-B-202 original;
SG-B-2xx rewrote print-queue notifications from an instant per-booking
push to a once-daily digest per owner). Route-level scheduling lives
in app.py's *_print_queue_digest jobs; these exercise message
composition and the send wrapper directly.
"""
from unittest import mock
from datetime import date

import core.services.notification_service as service


def test_format_thai_date_uses_the_consistent_short_thai_format():
    assert service.format_thai_date(date(2026, 8, 2)) == "2 ส.ค. 2569"


def test_booking_display_name_uses_both_names_when_both_present():
    assert service.booking_display_name(person1_name="สมชาย", person2_name="สมหญิง") == "สมชาย และ สมหญิง"


def test_booking_display_name_falls_back_to_customer_name_when_no_person_names():
    assert service.booking_display_name(customer_name="ลูกค้าทั่วไป") == "ลูกค้าทั่วไป"


def test_booking_display_name_uses_unspecified_label_when_no_names_at_all():
    assert service.booking_display_name() == "ไม่ระบุชื่อ"


def test_send_print_queue_digest_is_a_noop_for_empty_items_outside_an_active_ceremony():
    with mock.patch.object(service, "send_line_notification") as mock_send:
        success, err = service.send_print_queue_digest("muteteam", [])
    assert success is True
    assert err is None
    mock_send.assert_not_called()


def test_send_print_queue_digest_groups_pending_work_by_selected_price():
    items = [
        {"total_price": 269},
        {"total_price": 269},
        {"total_price": 999},
    ]

    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.send_print_queue_digest("muteteam", items, ceremony_names=["งานทดสอบ"])
    text = mock_send.call_args.args[1]
    assert "งานพิธี: งานทดสอบ" in text
    assert "สถานะ: มีรายการค้างปริ้น" in text
    assert "ราคา ฿269 จำนวน 2 ใบ" in text
    assert "ราคา ฿999 จำนวน 1 ใบ" in text
    assert "150AA010001" not in text
    assert "รหัสที่ต้องปริ้น:" not in text


def test_send_print_queue_digest_uses_page_display_name():
    items = [{"total_price": 269}]

    with mock.patch.object(service, "get_owner_display_name", return_value="สยามคเณศ ลาวใหม่"), \
         mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.send_print_queue_digest("laos", items)

    text = mock_send.call_args.args[1]
    assert "เพจ: สยามคเณศ ลาวใหม่" in text
    assert "ราคา ฿269 จำนวน 1 ใบ" in text
    assert "สถานะ: มีรายการค้างปริ้น" in text


def test_send_print_queue_digest_can_confirm_an_empty_queue_during_a_ceremony():
    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.send_print_queue_digest("mahabucha", [], ceremony_names=["งานมหาบูชา"], send_empty=True)

    text = mock_send.call_args.args[1]
    assert "งานพิธี: งานมหาบูชา" in text
    assert "สถานะ: ไม่มีรายการค้างปริ้น" in text


def test_send_print_queue_digest_returns_send_line_notification_result():
    with mock.patch.object(service, "send_line_notification", return_value=(False, "some error")):
        success, err = service.send_print_queue_digest(
            "muteteam", [{"total_price": 269}]
        )
    assert success is False
    assert err == "some error"
