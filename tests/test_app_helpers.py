"""
Unit tests for small, side-effect-free helper functions.

These are pure string-building helpers that don't touch the network,
Supabase, or LINE APIs, so they can be tested directly.
"""
from config import GITHUB_USERNAME, REPO_NAME, BRANCH
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
