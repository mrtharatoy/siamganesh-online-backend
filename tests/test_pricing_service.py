from unittest import mock

from core.services import pricing_service as service


def test_get_tier_name_map_returns_id_to_name_for_the_owner():
    response = mock.Mock(status_code=200)
    response.json.return_value = [{"value": {"laos": [
        {"id": "tier-1", "name": "แบบธรรมดา", "price": 267},
        {"id": "tier-2", "name": "แบบพิเศษ", "price": 999},
    ]}}]

    with mock.patch.object(service, "SUPABASE_URL", "https://project.supabase.co"), \
         mock.patch.object(service, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.get", return_value=response):
        assert service.get_tier_name_map("laos") == {"tier-1": "แบบธรรมดา", "tier-2": "แบบพิเศษ"}


def test_get_tier_name_map_is_empty_when_owner_has_no_tiers():
    response = mock.Mock(status_code=200)
    response.json.return_value = [{"value": {"laos": []}}]

    with mock.patch.object(service, "SUPABASE_URL", "https://project.supabase.co"), \
         mock.patch.object(service, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.get", return_value=response):
        assert service.get_tier_name_map("laos") == {}


def test_get_tier_name_map_falls_back_to_empty_when_supabase_is_not_configured():
    with mock.patch.object(service, "SUPABASE_URL", ""), \
         mock.patch.object(service, "SUPABASE_KEY", ""):
        assert service.get_tier_name_map("laos") == {}


def test_resolve_price_label_uses_tier_name_when_price_id_is_known():
    tier_map = {"tier-1": "แบบธรรมดา"}
    booking = {"tray_items": [{"price_id": "tier-1"}], "total_price": 267.43}
    assert service.resolve_price_label(tier_map, booking) == "แบบธรรมดา"


def test_resolve_price_label_falls_back_to_formatted_price_when_price_id_is_unknown():
    booking = {"tray_items": [{"price_id": "deleted-tier"}], "total_price": 267.43}
    assert service.resolve_price_label({}, booking) == "฿267"


def test_resolve_price_label_falls_back_to_formatted_price_for_legacy_bookings_without_price_id():
    booking = {"total_price": 269}
    assert service.resolve_price_label({"tier-1": "แบบธรรมดา"}, booking) == "฿269"


def test_resolve_price_label_reports_unspecified_when_price_is_missing_entirely():
    booking = {}
    assert service.resolve_price_label({}, booking) == "ไม่ระบุราคา"
