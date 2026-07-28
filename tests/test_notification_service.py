"""
Tests for core/services/notification_service.py (SG-B-202) -- the
print-queue message building extracted from notify_photo(). Route-level
behavior (including LINE token/group fallbacks) stays covered in
tests/test_route_notifications.py; these exercise message-composition
directly.
"""
from unittest import mock

import core.services.notification_service as service


def test_notify_print_queue_uses_both_names_when_both_present():
    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.notify_print_queue("muteteam", "150AA010001", person1_name="สมชาย", person2_name="สมหญิง")

    text = mock_send.call_args.args[1]
    assert "สมชาย และ สมหญิง" in text
    assert "150AA010001" in text


def test_notify_print_queue_falls_back_to_customer_name_when_no_person_names():
    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.notify_print_queue("muteteam", "150AA010001", customer_name="ลูกค้าทั่วไป")

    text = mock_send.call_args.args[1]
    assert "ลูกค้าทั่วไป" in text


def test_notify_print_queue_uses_unspecified_label_when_no_names_at_all():
    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.notify_print_queue("muteteam", "150AA010001")

    text = mock_send.call_args.args[1]
    assert "ไม่ระบุชื่อ" in text


def test_notify_print_queue_includes_tray_count_for_muteteam_only():
    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.notify_print_queue("muteteam", "150AA010001", tray_count=3)
    assert "จำนวน: 3 องค์เทพ" in mock_send.call_args.args[1]

    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.notify_print_queue("mahabucha", "150AA010001", tray_count=3)
    assert "จำนวน" not in mock_send.call_args.args[1]


def test_notify_print_queue_uses_display_name_and_no_tray_count_for_laos():
    with mock.patch.object(service, "send_line_notification", return_value=(True, None)) as mock_send:
        service.notify_print_queue("laos", "150AA010001", tray_count=3)
    text = mock_send.call_args.args[1]
    assert "เพจ: สยามคเณศ (ลาว)" in text
    assert "จำนวน" not in text


def test_notify_print_queue_returns_send_line_notification_result():
    with mock.patch.object(service, "send_line_notification", return_value=(False, "some error")):
        success, err = service.notify_print_queue("muteteam", "150AA010001")
    assert success is False
    assert err == "some error"
