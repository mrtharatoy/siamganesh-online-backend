from unittest import mock

from core.services import page_configuration_service as service


def test_uses_centrally_configured_page_label():
    response = mock.Mock(status_code=200)
    response.json.return_value = [{"value": {"muteteam": {"label": "มูเตทีม (รายวัน) ใหม่"}}}]

    with mock.patch.object(service, "SUPABASE_URL", "https://project.supabase.co"), \
         mock.patch.object(service, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.get", return_value=response):
        assert service.get_owner_display_name("muteteam") == "มูเตทีม (รายวัน) ใหม่"


def test_reads_the_central_enabled_state():
    response = mock.Mock(status_code=200)
    response.json.return_value = [{"value": {"mahabucha": {"enabled": False}}}]

    with mock.patch.object(service, "SUPABASE_URL", "https://project.supabase.co"), \
         mock.patch.object(service, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.get", return_value=response):
        assert service.is_owner_enabled("mahabucha") is False


def test_falls_back_to_registry_when_configuration_cannot_be_loaded():
    with mock.patch.object(service, "SUPABASE_URL", ""), \
         mock.patch.object(service, "SUPABASE_KEY", ""):
        assert service.get_owner_display_name("muteteam") == "มูเตทีม (รายวัน)"
