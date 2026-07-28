"""
Tests for core/owners.py, the centralized owner/page registry
introduced when adding the laos/ratchaprasong pages. Locks in that
PAGE_OWNERS/find_owner_by_page_id cover all 5 known owners and that
laos/ratchaprasong are wired up as "mahabucha style".
"""
from config import MAHABUCHA_PAGE_ID, MUTETEAM_PAGE_ID, LAOS_PAGE_ID, RATCHAPRASONG_PAGE_ID
from core.owners import OWNERS, PAGE_OWNERS, MAHABUCHA_STYLE_OWNERS, find_owner_by_page_id


def test_page_owners_includes_all_five_known_owners():
    assert set(PAGE_OWNERS) == {
        "mahabucha", "muteteam", "muteteam_ceremony", "laos", "ratchaprasong",
    }


def test_mahabucha_style_owners_groups_mahabucha_muteteam_ceremony_laos_ratchaprasong():
    assert set(MAHABUCHA_STYLE_OWNERS) == {"mahabucha", "muteteam_ceremony", "laos", "ratchaprasong"}
    assert "muteteam" not in MAHABUCHA_STYLE_OWNERS


def test_find_owner_by_page_id_matches_each_fb_page_owner():
    assert find_owner_by_page_id(MAHABUCHA_PAGE_ID) == "mahabucha"
    assert find_owner_by_page_id(MUTETEAM_PAGE_ID) == "muteteam"
    assert find_owner_by_page_id(LAOS_PAGE_ID) == "laos"
    assert find_owner_by_page_id(RATCHAPRASONG_PAGE_ID) == "ratchaprasong"


def test_find_owner_by_page_id_returns_none_for_unknown_page():
    assert find_owner_by_page_id("no-such-page") is None


def test_muteteam_ceremony_has_no_facebook_page_of_its_own():
    # It piggybacks on muteteam's FB page -- routed there by message
    # content, not by a distinct webhook page_id.
    assert OWNERS["muteteam_ceremony"].page_id is None


def test_laos_and_ratchaprasong_have_display_names_and_own_fb_pages():
    assert OWNERS["laos"].display_name == "สยามคเณศ (ลาว)"
    assert OWNERS["ratchaprasong"].display_name == "สยามคเณศ (ราชประสงค์)"
    assert OWNERS["laos"].page_id == LAOS_PAGE_ID
    assert OWNERS["ratchaprasong"].page_id == RATCHAPRASONG_PAGE_ID
