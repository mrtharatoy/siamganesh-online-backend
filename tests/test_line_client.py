"""
Tests for core/clients/line_client.py's fetch_quota (SG-B-201) -- moved
here from an inline nested function in core/blueprints/notifications.py
so /api/line-quota no longer builds LINE API requests directly.
get_line_token/send_line_notification are already covered indirectly
via tests/test_route_notifications.py.
"""
from unittest import mock

import core.clients.line_client as line_client


def test_get_line_token_returns_laos_token_when_configured():
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_LAOS", "laos-line-token"):
        assert line_client.get_line_token("laos") == "laos-line-token"


def test_get_line_token_returns_ratchaprasong_token_when_configured():
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_RATCHAPRASONG", "ratchaprasong-line-token"):
        assert line_client.get_line_token("ratchaprasong") == "ratchaprasong-line-token"


def test_send_line_notification_uses_mahabucha_group_for_laos_and_ratchaprasong():
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_LAOS", "laos-line-token"), \
         mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN_RATCHAPRASONG", "ratchaprasong-line-token"), \
         mock.patch.object(line_client, "LINE_GROUP_ID_MAHABUCHA", "mahabucha-group"), \
         mock.patch("requests.post", return_value=mock.Mock(status_code=200)) as mock_post:
        line_client.send_line_notification("laos", "hello")
        line_client.send_line_notification("ratchaprasong", "hello")

    groups_used = [call.kwargs["json"]["to"] for call in mock_post.call_args_list]
    assert groups_used == ["mahabucha-group", "mahabucha-group"]


def test_fetch_quota_returns_none_when_no_token():
    assert line_client.fetch_quota(None) is None
    assert line_client.fetch_quota("") is None


def test_fetch_quota_returns_usage_and_limit():
    usage_res = mock.Mock(status_code=200)
    usage_res.json.return_value = {"totalUsage": 42}
    limit_res = mock.Mock(status_code=200)
    limit_res.json.return_value = {"value": 1000}

    with mock.patch("requests.get", side_effect=[usage_res, limit_res]):
        result = line_client.fetch_quota("fake-token")

    assert result == {"usage": 42, "limit": 1000}


def test_fetch_quota_defaults_to_zero_when_line_api_errors():
    usage_res = mock.Mock(status_code=500)
    limit_res = mock.Mock(status_code=500)

    with mock.patch("requests.get", side_effect=[usage_res, limit_res]):
        result = line_client.fetch_quota("fake-token")

    assert result == {"usage": 0, "limit": 0}


def test_fetch_quota_returns_none_on_network_exception():
    with mock.patch("requests.get", side_effect=RuntimeError("network down")):
        assert line_client.fetch_quota("fake-token") is None
