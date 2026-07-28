"""
Tests for process_ceremony_flow()'s message-parsing / code-matching logic
-- the core "does this customer message contain a valid booking code, and
does it match a cached image" business logic used by both the Mahabucha
and Muteteam bots.

This logic now lives in core/services/messenger_service.py (SG-B-102,
moved out of app.py). process_ceremony_flow() also sends Facebook
messages and reads booking rows from Supabase. We avoid real network
calls without mocking away the logic under test by relying on the
*actual* early-return guards already present in the code:
  - SUPABASE_URL/SUPABASE_KEY are forced empty in conftest.py, so
    get_booking_by_code() / get_system_setting() return their default
    values immediately (no HTTP call).
  - We pass a page_id that doesn't match any configured Facebook page,
    so get_page_token() returns None and send_fb_action() short-circuits
    before making any HTTP call.
The one boundary we do spy on (via mock.patch) is send_fb_action, purely
to assert *what* the code decided to send -- not to fake its behavior.
It must be patched on core.services.messenger_service (where
process_ceremony_flow looks it up), not on the app module -- app.py only
re-exports the same function object via `from
core.services.messenger_service import process_ceremony_flow, ...`,
which doesn't change where process_ceremony_flow's own global lookups
resolve.
"""
from unittest import mock

import core.services.messenger_service as messenger_service

UNKNOWN_PAGE_ID = "no-such-page"


def test_returns_false_when_message_has_no_code_like_pattern(app_module):
    result = messenger_service.process_ceremony_flow(
        "user1", "สวัสดีครับ ขอบคุณสำหรับพิธีนะครับ", UNKNOWN_PAGE_ID, "mahabucha"
    )
    assert result is False


def test_returns_true_and_reports_unknown_code_when_not_in_cache(app_module):
    # No test in this file ever populates CACHED_FILES with this code,
    # so it should fall into the "unknown_codes" / not-found branch.
    with mock.patch.object(messenger_service, "send_fb_action", return_value=(True, "")) as mock_send:
        result = messenger_service.process_ceremony_flow(
            "user1", "รหัส 150ab999 ครับ", UNKNOWN_PAGE_ID, "mahabucha"
        )
    assert result is True
    # The "not found" message should have been sent (auto_reply_not_found
    # defaults to True since Supabase isn't configured in tests).
    assert mock_send.called
    sent_texts = [call.args[3] for call in mock_send.call_args_list if call.args[2] == "text"]
    assert any("ไม่พบภาพถาดถวาย" in t for t in sent_texts)


def test_matches_code_prefix_against_cached_filenames(app_module):
    with mock.patch.dict(
        messenger_service.CACHED_FILES,
        {"mahabucha": {"150ab01": "150ab01.jpg"}},
    ), mock.patch.object(messenger_service, "send_fb_action", return_value=(True, "")) as mock_send:
        result = messenger_service.process_ceremony_flow(
            "user1", "รหัส 150ab01 ครับ", UNKNOWN_PAGE_ID, "mahabucha"
        )

    assert result is True
    # It should have sent the intro text, the code-label text, and the image.
    sent_calls = [(call.args[2], call.args[3]) for call in mock_send.call_args_list]
    image_sends = [payload for (dtype, payload) in sent_calls if dtype == "image"]
    assert any("150ab01.jpg" in payload for payload in image_sends)
    label_sends = [payload for (dtype, payload) in sent_calls if dtype == "text"]
    assert any("150AB01" in payload for payload in label_sends)  # code_key.upper()


def test_ignores_codes_embedded_in_longer_digit_runs(app_module):
    # The regex uses (?<!\d)...(?!\d) lookarounds so a code-like pattern
    # that's part of a longer number shouldn't match on its own.
    result = messenger_service.process_ceremony_flow(
        "user1", "เบอร์โทร 0812345678", UNKNOWN_PAGE_ID, "mahabucha"
    )
    assert result is False


def test_extracts_multiple_distinct_codes_from_one_message(app_module):
    with mock.patch.object(messenger_service, "send_fb_action", return_value=(True, "")) as mock_send:
        result = messenger_service.process_ceremony_flow(
            "user1", "รหัส 150ab01 กับ 269cd02 ครับ", UNKNOWN_PAGE_ID, "mahabucha"
        )
    assert result is True
    # Both codes are unknown (not in cache), so both should show up in a
    # single "not found" message rather than one per code.
    text_sends = [call.args[3] for call in mock_send.call_args_list if call.args[2] == "text"]
    assert any("ไม่พบภาพถาดถวาย" in t for t in text_sends)
