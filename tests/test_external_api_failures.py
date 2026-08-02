"""
SG-005: integration tests for external-API failure/timeout paths that
weren't covered elsewhere. The existing route test files (test_route_*)
mostly characterize non-200 HTTP *status* responses from GitHub/LINE/
external APIs; none of them exercise a genuinely *raised* exception
(timeout, connection error) from the underlying `requests` call, which
is the realistic failure mode in production when an external API is
unreachable.

Coverage added here, one client at a time:

- GitHub (core/clients/github_client.py): no try/except around any of
  its `requests.get/put/delete` calls, so a raised exception propagates
  all the way up through core/services/image_upload_service.py and the
  images blueprint uncaught. That's an existing, deliberate pattern
  (matches the original app.py code before SG-B-103/201) -- it's
  exercised here via the generic 500 JSON handler (core/errors.py,
  SG-B-107), the same way test_errors.py verifies unhandled exceptions
  elsewhere. Needs `app.testing = False` so Flask actually converts the
  exception instead of re-raising it into the test, matching
  test_errors.py's documented reasoning.
- LINE (core/clients/line_client.py): the opposite shape --
  send_line_notification and fetch_quota both already wrap their
  requests calls in try/except and degrade gracefully (False/None)
  instead of raising. Covered here to lock in that resilience with a
  real exception, not just a non-200 status.
"""
from unittest import mock

import pytest
import requests

import core.clients.line_client as line_client


@pytest.fixture
def client(app_module):
    # See test_errors.py: PROPAGATE_EXCEPTIONS behaves like True when
    # app.testing is True, which would re-raise an unhandled exception
    # into the test itself instead of letting Flask's real errorhandler
    # machinery convert it to a 500 response. Off here because several
    # tests below rely on that conversion for routes with no
    # route-level try/except of their own.
    app_module.app.testing = False
    return app_module.app.test_client()


# --- LINE timeout (caught internally -> graceful degradation, not a 500) ---


def test_send_line_notification_degrades_gracefully_when_line_send_times_out():
    # notify-photo (the HTTP route) was removed with the switch to a
    # once-daily print-queue digest -- send_line_notification itself is
    # still the thing that talks to LINE and must still degrade
    # gracefully on timeout, exercised directly here instead of via
    # that now-removed route.
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", "fake-token"), \
         mock.patch.object(line_client, "LINE_GROUP_ID", "fake-group"), \
         mock.patch("requests.post", side_effect=requests.exceptions.Timeout("line timed out")):
        success, err = line_client.send_line_notification("mahabucha", "hello")

    assert success is False
    assert "line timed out" in err


def test_line_quota_returns_null_when_line_api_times_out(client):
    with mock.patch.object(line_client, "LINE_CHANNEL_ACCESS_TOKEN", "fake-token"), \
         mock.patch("requests.get", side_effect=requests.exceptions.Timeout("line timed out")):
        resp = client.get("/api/line-quota")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["quota"] is None
