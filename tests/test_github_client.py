"""
Tests for core/clients/github_client.py (SG-B-201).
"""
from unittest import mock

import core.clients.github_client as github_client


def test_get_file_sha_returns_sha_when_file_exists():
    fake = mock.Mock(status_code=200)
    fake.json.return_value = {"sha": "abc123"}
    with mock.patch("requests.get", return_value=fake) as mock_get:
        sha = github_client.get_file_sha("images/muteteam/x.jpg")
    assert sha == "abc123"
    called_url = mock_get.call_args.args[0]
    assert "?ref=" not in called_url


def test_get_file_sha_returns_none_when_file_missing():
    fake = mock.Mock(status_code=404)
    with mock.patch("requests.get", return_value=fake):
        assert github_client.get_file_sha("images/muteteam/x.jpg") is None


def test_get_file_sha_at_ref_includes_ref_query_param():
    fake = mock.Mock(status_code=200)
    fake.json.return_value = {"sha": "def456"}
    with mock.patch("requests.get", return_value=fake) as mock_get:
        sha, status = github_client.get_file_sha_at_ref("images/muteteam/x.jpg", "main")
    assert sha == "def456"
    assert status == 200
    assert mock_get.call_args.args[0].endswith("?ref=main")


def test_get_file_sha_at_ref_returns_none_and_status_when_missing():
    fake = mock.Mock(status_code=404)
    with mock.patch("requests.get", return_value=fake):
        sha, status = github_client.get_file_sha_at_ref("images/muteteam/x.jpg", "main")
    assert sha is None
    assert status == 404


def test_put_file_success():
    fake = mock.Mock(status_code=201)
    with mock.patch("requests.put", return_value=fake) as mock_put:
        success, error = github_client.put_file("images/muteteam/x.jpg", "ZmFrZQ==", "msg", sha="abc")
    assert success is True
    assert error is None
    payload = mock_put.call_args.kwargs["json"]
    assert payload["sha"] == "abc"
    assert payload["content"] == "ZmFrZQ=="


def test_put_file_failure_returns_github_error_message():
    fake = mock.Mock(status_code=422)
    fake.json.return_value = {"message": "Validation Failed"}
    with mock.patch("requests.put", return_value=fake):
        success, error = github_client.put_file("images/muteteam/x.jpg", "ZmFrZQ==", "msg")
    assert success is False
    assert error == "Validation Failed"


def test_delete_file_success():
    fake = mock.Mock(status_code=200)
    with mock.patch("requests.delete", return_value=fake) as mock_delete:
        success, error = github_client.delete_file("images/muteteam/x.jpg", "abc123", "delete msg")
    assert success is True
    assert error is None
    payload = mock_delete.call_args.kwargs["json"]
    assert payload["sha"] == "abc123"


def test_delete_file_failure_returns_github_error_message():
    fake = mock.Mock(status_code=404)
    fake.json.return_value = {"message": "not found"}
    with mock.patch("requests.delete", return_value=fake):
        success, error = github_client.delete_file("images/muteteam/x.jpg", "abc123", "delete msg")
    assert success is False
    assert error == "not found"
