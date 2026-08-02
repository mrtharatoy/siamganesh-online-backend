"""
Tests for app.py's _owner_print_queue_digest -- the 16:00 report sent
only on the day before and the day of a ceremony. Message composition
itself is tested in tests/test_notification_service.py; these exercise
the setting gate, ceremony-window filtering, and empty confirmation.

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


def _scheduled_date(offset=0):
    return (datetime.now(timezone(timedelta(hours=7))).date() + timedelta(days=offset)).isoformat()


def test_digest_skipped_when_owner_explicitly_disabled(app_module, supabase_configured):
    with mock.patch("requests.get", return_value=_settings_response({"mahabucha": False})) as mock_get, \
         mock.patch.object(app_module, "send_print_queue_digest") as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    mock_send.assert_not_called()
    # Only the settings fetch happens -- bails out before querying bookings.
    assert mock_get.call_count == 1


def test_digest_sends_every_pending_price_to_the_template(app_module, supabase_configured):
    bookings = [
        {"gallery_id": "event-1", "total_price": 269},
        {"gallery_id": "event-1", "total_price": 999},
    ]

    with mock.patch(
        "requests.get",
        side_effect=[_settings_response({"mahabucha": True}), _bookings_response([{"id": "event-1", "caption": "งานมหาบูชา", "event_date": _scheduled_date(1)}]), _bookings_response(bookings)],
    ), mock.patch.object(app_module, "send_print_queue_digest", return_value=(True, None)) as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    mock_send.assert_called_once()
    owner_arg, items_arg = mock_send.call_args.args
    assert owner_arg == "mahabucha"
    assert {item["total_price"] for item in items_arg} == {269, 999}
    assert mock_send.call_args.kwargs == {"ceremony_names": ["งานมหาบูชา"], "send_empty": True}


def test_digest_sends_empty_confirmation_when_ceremony_is_today_or_tomorrow(app_module, supabase_configured):

    with mock.patch(
        "requests.get",
        side_effect=[_settings_response({"mahabucha": True}), _bookings_response([{"id": "event-1", "caption": "งานมหาบูชา", "event_date": _scheduled_date()}]), _bookings_response([])],
    ), mock.patch.object(app_module, "send_print_queue_digest", return_value=(True, None)) as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    mock_send.assert_called_once_with("mahabucha", [], ceremony_names=["งานมหาบูชา"], send_empty=True)


def test_digest_skips_when_no_ceremony_is_today_or_tomorrow(app_module, supabase_configured):
    with mock.patch(
        "requests.get",
        side_effect=[_settings_response({"mahabucha": True}), _bookings_response([{"id": "event-1", "caption": "งานอนาคต", "event_date": "2999-01-01"}])],
    ), mock.patch.object(app_module, "send_print_queue_digest") as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    mock_send.assert_not_called()


def test_digest_falls_back_to_legacy_enabled_shape(app_module, supabase_configured):
    # A setting still shaped as the old single-flag `{"enabled": bool}`
    # (predating the per-owner keys) must still gate every owner.
    bookings = [
        {"gallery_id": "event-1", "total_price": 269},
    ]

    with mock.patch(
        "requests.get",
        side_effect=[_settings_response({"enabled": True}), _bookings_response([{"id": "event-1", "caption": "งานลาว", "event_date": _scheduled_date()}]), _bookings_response(bookings)],
    ), mock.patch.object(app_module, "send_print_queue_digest", return_value=(True, None)) as mock_send:
        app_module._owner_print_queue_digest("laos")

    mock_send.assert_called_once()


def test_digest_legacy_enabled_false_disables_every_owner(app_module, supabase_configured):
    with mock.patch("requests.get", return_value=_settings_response({"enabled": False})) as mock_get, \
         mock.patch.object(app_module, "send_print_queue_digest") as mock_send:
        app_module._owner_print_queue_digest("ratchaprasong")

    mock_send.assert_not_called()
    assert mock_get.call_count == 1


def test_digest_ignores_waiting_print_from_a_different_ceremony(app_module, supabase_configured):
    bookings = [
        {"gallery_id": "scheduled", "total_price": 269},
        {"gallery_id": "old-event", "total_price": 999},
    ]
    with mock.patch(
        "requests.get",
        side_effect=[
            _settings_response({"mahabucha": True}),
            _bookings_response([{"id": "scheduled", "caption": "งานพรุ่งนี้", "event_date": _scheduled_date(1)}]),
            _bookings_response(bookings),
        ],
    ), mock.patch.object(app_module, "send_print_queue_digest", return_value=(True, None)) as mock_send:
        app_module._owner_print_queue_digest("mahabucha")

    assert mock_send.call_args.args[1] == [{"total_price": 269}]
