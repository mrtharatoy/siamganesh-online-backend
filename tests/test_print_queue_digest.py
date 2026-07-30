"""
Tests for app.py's _owner_print_queue_digest (SG-B-2xx) -- the
once-daily 16:00 print-queue digest that replaced the instant
per-booking "notify-photo" push. Message composition itself is tested
in tests/test_notification_service.py; these exercise the gating
(line_notify_group setting) and the created-today/queued-today booking
filter.

SUPABASE_URL/SUPABASE_KEY are empty strings in the test env
(conftest.py) so the function's `if not SUPABASE_URL or not
SUPABASE_KEY: return` guard fires by default -- every test here patches
both to a truthy value first.
"""
from datetime import datetime, timezone, timedelta
from unittest import mock

import pytest


@pytest.fixture
def supabase_configured(app_module):
    with mock.patch.object(app_module, "SUPABASE_URL", "https://example.supabase.co"), \
         mock.patch.object(app_module, "SUPABASE_KEY", "fake-key"):
        yield


def _settings_response(value):
    return mock.Mock(status_code=200, json=lambda: [{"value": value}])


def _bookings_response(bookings):
    return mock.Mock(status_code=200, json=lambda: bookings)


def _iso_now_th():
    return datetime.now(timezone(timedelta(hours=7))).isoformat()


def _iso_yesterday_th():
    return (datetime.now(timezone(timedelta(hours=7))) - timedelta(days=1)).isoformat()


def test_digest_skipped_when_owner_explicitly_disabled(app_module, supabase_configured):
    with mock.patch("requests.get", return_value=_settings_response({"mahabucha": False})) as mock_get, \
         mock.patch.object(app_module, "send_print_queue_digest") as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    mock_send.assert_not_called()
    # Only the settings fetch happens -- bails out before querying bookings.
    assert mock_get.call_count == 1


def test_digest_sends_for_bookings_created_or_queued_today(app_module, supabase_configured):
    bookings = [
        {  # created today -> included
            "booking_code": "150AA010001", "customer_name": "สมชาย", "person1_name": None,
            "person2_name": None, "tray_count": 1, "tray_items": [{"price_id": "p1"}],
            "created_at": _iso_now_th(), "activity_logs": [],
        },
        {  # created yesterday, queued today -> included
            "booking_code": "150AA010002", "customer_name": "สมหญิง", "person1_name": None,
            "person2_name": None, "tray_count": 1, "tray_items": [{"price_id": "p1"}],
            "created_at": _iso_yesterday_th(),
            "activity_logs": [{"action": "waiting_print", "by": "admin", "timestamp": _iso_now_th()}],
        },
        {  # created yesterday, never queued today -> excluded
            "booking_code": "150AA010003", "customer_name": "ไม่เกี่ยว", "person1_name": None,
            "person2_name": None, "tray_count": 1, "tray_items": [{"price_id": "p1"}],
            "created_at": _iso_yesterday_th(), "activity_logs": [],
        },
    ]

    with mock.patch(
        "requests.get",
        side_effect=[_settings_response({"mahabucha": True}), _bookings_response(bookings)],
    ), mock.patch.object(app_module, "send_print_queue_digest", return_value=(True, None)) as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    mock_send.assert_called_once()
    owner_arg, items_arg = mock_send.call_args.args
    assert owner_arg == "mahabucha"
    codes = {item["booking_code"] for item in items_arg}
    assert codes == {"150AA010001", "150AA010002"}


def test_digest_does_not_send_when_nothing_qualifies_today(app_module, supabase_configured):
    bookings = [
        {
            "booking_code": "150AA010003", "customer_name": "ไม่เกี่ยว", "person1_name": None,
            "person2_name": None, "tray_count": 1, "tray_items": [{"price_id": "p1"}],
            "created_at": _iso_yesterday_th(), "activity_logs": [],
        },
    ]

    with mock.patch(
        "requests.get",
        side_effect=[_settings_response({"mahabucha": True}), _bookings_response(bookings)],
    ), mock.patch.object(app_module, "send_print_queue_digest") as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    mock_send.assert_not_called()


def test_digest_falls_back_to_legacy_enabled_shape(app_module, supabase_configured):
    # A setting still shaped as the old single-flag `{"enabled": bool}`
    # (predating the per-owner keys) must still gate every owner.
    bookings = [
        {
            "booking_code": "150AA010001", "customer_name": "สมชาย", "person1_name": None,
            "person2_name": None, "tray_count": 1, "tray_items": [{"price_id": "p1"}],
            "created_at": _iso_now_th(), "activity_logs": [],
        },
    ]

    with mock.patch(
        "requests.get",
        side_effect=[_settings_response({"enabled": True}), _bookings_response(bookings)],
    ), mock.patch.object(app_module, "send_print_queue_digest", return_value=(True, None)) as mock_send:
        app_module._owner_print_queue_digest("laos")

    mock_send.assert_called_once()


def test_digest_legacy_enabled_false_disables_every_owner(app_module, supabase_configured):
    with mock.patch("requests.get", return_value=_settings_response({"enabled": False})) as mock_get, \
         mock.patch.object(app_module, "send_print_queue_digest") as mock_send:
        app_module._owner_print_queue_digest("ratchaprasong")

    mock_send.assert_not_called()
    assert mock_get.call_count == 1
