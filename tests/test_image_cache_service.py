"""
Tests for core/services/image_cache_service.py (SG-B-103a).

This module owns the GitHub-backed image cache shared by the
messenger, images, and search routes. `is_loaded()`/`get_last_refresh()`
/`touch_last_refresh()` are function-based accessors specifically so
that other modules calling them always see the current state -- a
plain re-exported bool/float name would go stale across a module
boundary the moment this module reassigns its own copy. These tests
lock in that the accessors behave correctly and that update_file_list()
does NOT touch the refresh timestamp itself (callers own that, exactly
matching the original app.py control flow being preserved).
"""
from unittest import mock

import core.services.image_cache_service as image_cache_service


@mock.patch.object(image_cache_service, "_files_loaded", False)
@mock.patch.object(image_cache_service, "_last_cache_refresh", 0)
def test_is_loaded_false_and_last_refresh_zero_before_any_update():
    assert image_cache_service.is_loaded() is False
    assert image_cache_service.get_last_refresh() == 0


@mock.patch.object(image_cache_service, "_files_loaded", False)
def test_update_file_list_marks_loaded_true_but_does_not_touch_refresh_timestamp():
    # Callers are responsible for calling touch_last_refresh() themselves
    # right after update_file_list(), under their own lock -- this was
    # true in the original app.py (LAST_CACHE_REFRESH was only ever set
    # by call sites, never inside update_file_list) and must stay true.
    with mock.patch.object(image_cache_service, "_last_cache_refresh", 12345), \
         mock.patch("requests.get", side_effect=RuntimeError("no network in this test")):
        image_cache_service.update_file_list()
        assert image_cache_service.is_loaded() is True
        assert image_cache_service.get_last_refresh() == 12345


def test_touch_last_refresh_sets_current_time():
    with mock.patch.object(image_cache_service, "_last_cache_refresh", 0), \
         mock.patch("time.time", return_value=999.5):
        image_cache_service.touch_last_refresh()
        assert image_cache_service.get_last_refresh() == 999.5


def test_update_file_list_populates_cached_files_and_total_size_per_page():
    fake_response = mock.Mock(status_code=200)
    fake_response.json.return_value = [
        {"type": "file", "name": "150AA010001.jpg", "size": 100},
        {"type": "file", "name": ".keep", "size": 0},
        {"type": "dir", "name": "subfolder", "size": 0},
    ]
    empty_response = mock.Mock(status_code=200)
    empty_response.json.return_value = []

    with mock.patch.object(image_cache_service, "CACHED_FILES", {}), \
         mock.patch.object(image_cache_service, "TOTAL_IMAGES_SIZE", {}), \
         mock.patch.object(image_cache_service, "_files_loaded", False), \
         mock.patch(
             "requests.get",
             side_effect=[fake_response, empty_response, empty_response],
         ):
        image_cache_service.update_file_list()

        # Assertions must stay inside the `with` block: mock.patch.object
        # restores the pre-patch value the moment the block exits, so
        # checking image_cache_service.CACHED_FILES afterwards would see
        # the ORIGINAL (session-import-time) dict, not what this test set up.
        assert image_cache_service.CACHED_FILES["mahabucha"] == {"150aa010001": "150AA010001.jpg"}
        assert image_cache_service.TOTAL_IMAGES_SIZE["mahabucha"] == 100
        assert image_cache_service.is_loaded() is True


def test_update_file_list_tolerates_a_failed_page_without_raising():
    with mock.patch.object(image_cache_service, "CACHED_FILES", {"mahabucha": {"old": "old.jpg"}}), \
         mock.patch.object(image_cache_service, "_files_loaded", False), \
         mock.patch("requests.get", side_effect=RuntimeError("network down")):
        image_cache_service.update_file_list()  # must not raise

        # A page that errored keeps its previous cache entry untouched.
        assert image_cache_service.CACHED_FILES["mahabucha"] == {"old": "old.jpg"}
        assert image_cache_service.is_loaded() is True


def test_get_image_url_builds_expected_raw_github_url():
    url = image_cache_service.get_image_url("mahabucha", "150AA010001.jpg")
    assert url == (
        f"https://raw.githubusercontent.com/{image_cache_service.GITHUB_USERNAME}"
        f"/{image_cache_service.REPO_NAME}/{image_cache_service.BRANCH}/images/mahabucha/150AA010001.jpg"
    )
