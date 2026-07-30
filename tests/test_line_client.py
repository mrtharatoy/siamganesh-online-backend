"""
Tests for core/clients/line_client.py -- send_line_notification and
fetch_quota (SG-B-201/SG-B-2xx). All 5 owners now share a single LINE
channel token and group (LINE_CHANNEL_ACCESS_TOKEN/LINE_GROUP_ID), so
send_line_notification no longer branches on `owner` for credential
lookup -- these tests confirm every owner routes to that same
token/group, and that a missing token/group is reported per the
`owner` passed in (for logging) without changing which credentials
are used.
"""
from unittest import mock

import core.clients.line_client as line_client


def test_send_line_notification_uses_shared_token_and_group_for_every_owner():
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", "shared-token"), \
         mock.patch.object(line_client, "LINE_GROUP_ID", "shared-group"), \
         mock.patch("requests.post", return_value=mock.Mock(status_code=200)) as mock_post:
        for owner in ("mahabucha", "muteteam", "muteteam_ceremony", "laos", "ratchaprasong"):
            line_client.send_line_notification(owner, "hello")

    groups_used = [call.kwargs["json"]["to"] for call in mock_post.call_args_list]
    tokens_used = [call.kwargs["headers"]["Authorization"] for call in mock_post.call_args_list]
    assert groups_used == ["shared-group"] * 5
    assert tokens_used == ["Bearer shared-token"] * 5


def test_send_line_notification_fails_when_token_missing():
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", None):
        success, err = line_client.send_line_notification("mahabucha", "hello")
    assert success is False
    assert "LINE_CHANNEL_ACCESS_TOKEN" in err


def test_send_line_notification_fails_when_group_missing():
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", "shared-token"), \
         mock.patch.object(line_client, "LINE_GROUP_ID", None):
        success, err = line_client.send_line_notification("mahabucha", "hello")
    assert success is False
    assert "LINE_GROUP_ID" in err


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
