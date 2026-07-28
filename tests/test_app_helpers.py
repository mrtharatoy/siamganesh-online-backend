"""
Unit tests for small, side-effect-free helper functions.

These are pure string-building / lookup helpers that don't touch the
network, Supabase, or Facebook/LINE APIs, so they can be tested directly.

get_page_token() moved to core/clients/facebook_client.py (SG-B-102) and
has no remaining direct import in app.py, so it's tested via that module
directly rather than through app_module.
"""
from config import MAHABUCHA_PAGE_ID, MUTETEAM_PAGE_ID, GITHUB_USERNAME, REPO_NAME, BRANCH
from core.clients.facebook_client import get_page_token


def test_get_image_url_builds_expected_raw_github_url(app_module):
    # get_image_url still has a direct import in app.py (search_api,
    # system_status use it), but GITHUB_USERNAME/REPO_NAME/BRANCH no
    # longer do -- read those from config directly instead.
    url = app_module.get_image_url("mahabucha", "150AA010001.jpg")
    assert url == (
        f"https://raw.githubusercontent.com/{GITHUB_USERNAME}"
        f"/{REPO_NAME}/{BRANCH}/images/mahabucha/150AA010001.jpg"
    )


def test_get_page_token_returns_mahabucha_token_for_mahabucha_page():
    assert get_page_token(MAHABUCHA_PAGE_ID) == "test-mahabucha-token"


def test_get_page_token_returns_muteteam_token_for_muteteam_page():
    assert get_page_token(MUTETEAM_PAGE_ID) == "test-muteteam-token"


def test_get_page_token_compares_as_strings():
    # page_id often arrives as a string from the webhook payload even
    # though the configured ID might look numeric; str(...) comparison
    # should still match.
    assert get_page_token(str(MAHABUCHA_PAGE_ID)) == "test-mahabucha-token"


def test_get_page_token_returns_none_for_unknown_page(app_module):
    assert get_page_token("9999999999") is None


def test_generate_thank_you_message_fallback_uses_generic_name_when_no_names(app_module):
    # GEMINI_API_KEY is forced empty in conftest, so this always takes
    # the deterministic fallback() branch (no Gemini network call).
    msg = app_module.generate_thank_you_message("150AA010001")
    assert msg == (
        "[PHOTO] ขออนุญาตส่งมอบความสิริมงคลแด่คุณผู้มีจิตศรัทธาครับ "
        "ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ 'มูเตทีม' นะครับ "
    )


def test_generate_thank_you_message_fallback_includes_single_name(app_module):
    msg = app_module.generate_thank_you_message("150AA010001", person1_name="สมชาย")
    assert "คุณสมชาย" in msg
    assert "ขออนุญาตส่งมอบความสิริมงคล" in msg


def test_generate_thank_you_message_fallback_includes_both_names(app_module):
    msg = app_module.generate_thank_you_message(
        "150AA010001", person1_name="สมชาย", person2_name="สมหญิง"
    )
    assert "สมชายและสมหญิง" in msg
