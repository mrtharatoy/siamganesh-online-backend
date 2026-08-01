"""
Unit tests for small, side-effect-free helper functions.

These are pure string-building helpers that don't touch the network,
Supabase, or LINE APIs, so they can be tested directly.
"""
from config import GITHUB_USERNAME, REPO_NAME, BRANCH
from core.services.ai_service import generate_thank_you_message
from core.services.image_cache_service import get_image_url


def test_get_image_url_builds_expected_raw_github_url():
    # get_image_url has no remaining direct import in app.py now that
    # search_api/system_status moved to core/blueprints/system.py
    # (SG-B-106) -- test it directly from image_cache_service instead.
    url = get_image_url("mahabucha", "150AA010001.jpg")
    assert url == (
        f"https://raw.githubusercontent.com/{GITHUB_USERNAME}"
        f"/{REPO_NAME}/{BRANCH}/images/mahabucha/150AA010001.jpg"
    )


def test_generate_thank_you_message_fallback_uses_generic_name_when_no_names():
    # generate_thank_you_message always returns the static template now
    # that the Gemini branch has been removed.
    msg = generate_thank_you_message("150AA010001")
    assert msg == (
        "[PHOTO] ขออนุญาตส่งมอบความสิริมงคลแด่คุณผู้มีจิตศรัทธาครับ "
        "ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ 'มูเตทีม' นะครับ "
    )


def test_generate_thank_you_message_fallback_includes_single_name():
    msg = generate_thank_you_message("150AA010001", person1_name="สมชาย")
    assert "คุณสมชาย" in msg
    assert "ขออนุญาตส่งมอบความสิริมงคล" in msg


def test_generate_thank_you_message_fallback_includes_both_names():
    msg = generate_thank_you_message(
        "150AA010001", person1_name="สมชาย", person2_name="สมหญิง"
    )
    assert "สมชายและสมหญิง" in msg
