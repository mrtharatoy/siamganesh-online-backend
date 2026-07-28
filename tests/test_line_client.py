"""
Tests for core/clients/line_client.py's fetch_quota (SG-B-201) -- moved
here from an inline nested function in core/blueprints/notifications.py
so /api/line-quota no longer builds LINE API requests directly.
get_line_token/send_line_notification are already covered indirectly
via tests/test_route_notifications.py.
"""
from unittest import mock

import core.clients.line_client as line_client


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
