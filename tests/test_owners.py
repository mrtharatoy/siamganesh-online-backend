"""
Tests for core/owners.py, the centralized owner registry. Locks in that
PAGE_OWNERS covers all 5 known owners and that laos/ratchaprasong are
wired up as "mahabucha style".
"""
from core.owners import OWNERS, PAGE_OWNERS, MAHABUCHA_STYLE_OWNERS


def test_page_owners_includes_all_five_known_owners():
    assert set(PAGE_OWNERS) == {
        "mahabucha", "muteteam", "muteteam_ceremony", "laos", "ratchaprasong",
    }


def test_mahabucha_style_owners_groups_mahabucha_muteteam_ceremony_laos_ratchaprasong():
    assert set(MAHABUCHA_STYLE_OWNERS) == {"mahabucha", "muteteam_ceremony", "laos", "ratchaprasong"}
    assert "muteteam" not in MAHABUCHA_STYLE_OWNERS


def test_laos_and_ratchaprasong_have_display_names():
    assert OWNERS["laos"].display_name == "สยามคเณศ (ลาว)"
    assert OWNERS["ratchaprasong"].display_name == "สยามคเณศ (ราชประสงค์)"
