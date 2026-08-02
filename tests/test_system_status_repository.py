"""
Tests for core/repositories/system_status_repository.py (SG-B-202).
"""
from unittest import mock

import core.repositories.system_status_repository as repo


def test_check_database_health_defaults_when_supabase_not_configured():
    assert repo.check_database_health() == {
        "status": "error", "latency_ms": 0, "total_bookings": 0,
    }


def test_check_database_health_ok_with_total_bookings():
    fake_get = mock.Mock(status_code=200)
    fake_get.raise_for_status = mock.Mock()
    fake_head = mock.Mock()
    fake_head.headers = {"Content-Range": "0-0/42"}

    with mock.patch.object(repo, "SUPABASE_URL", "https://x.supabase.co"), \
         mock.patch.object(repo, "SUPABASE_KEY", "fake-key"), \
         mock.patch("requests.get", return_value=fake_get), \
         mock.patch("requests.head", return_value=fake_head):
        result = repo.check_database_health()

    assert result["status"] == "ok"
    assert result["total_bookings"] == 42
    assert result["latency_ms"] >= 0


def test_check_database_health_error_when_request_raises():
    with mock.patch.object(repo, "SUPABASE_URL", "https://x.supabase.co"), \
         mock.patch.object(repo, "SUPABASE_KEY", "fake-key"), \
         mock.patch("requests.get", side_effect=RuntimeError("network down")):
        result = repo.check_database_health()

    assert result == {"status": "error", "latency_ms": 0, "total_bookings": 0}


def test_get_supabase_storage_stats_counts_files_and_recurses_into_folders():
    top_level = mock.Mock(status_code=200)
    top_level.json.return_value = [
        {"id": "file-1", "metadata": {"size": 100}},
        {"id": None, "name": "subfolder"},
    ]
    sub_level = mock.Mock(status_code=200)
    sub_level.json.return_value = [
        {"id": "file-2", "metadata": {"size": 50}},
    ]

    with mock.patch.object(repo, "SUPABASE_URL", "https://x.supabase.co"), \
         mock.patch.object(repo, "SUPABASE_KEY", "fake-key"), \
         mock.patch("requests.post", side_effect=[top_level, sub_level]):
        count, size = repo.get_supabase_storage_stats("portfolio")

    assert count == 2
    assert size == 150


def test_get_supabase_usage_metrics_reads_aggregate_rpc_only():
    response = mock.Mock()
    response.raise_for_status = mock.Mock()
    response.json.return_value = [{
        "database_size_bytes": "31457280",
        "file_storage_bytes": 191889408,
        "file_storage_count": 86,
        "monthly_active_users": 7,
    }]

    with mock.patch.object(repo, "SUPABASE_URL", "https://x.supabase.co"), \
         mock.patch.object(repo, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.post", return_value=response) as post:
        result = repo.get_supabase_usage_metrics()

    assert result == {
        "available": True,
        "database_size_bytes": 31457280,
        "file_storage_bytes": 191889408,
        "file_storage_count": 86,
        "monthly_active_users": 7,
    }
    assert post.call_args.args[0].endswith("/rest/v1/rpc/get_system_usage_metrics")


def test_get_supabase_usage_metrics_stays_unavailable_before_migration():
    with mock.patch.object(repo, "SUPABASE_URL", "https://x.supabase.co"), \
         mock.patch.object(repo, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.post", side_effect=repo.requests.RequestException("missing rpc")):
        result = repo.get_supabase_usage_metrics()

    assert result["available"] is False
