from datetime import datetime
from unittest import mock

from core.services import image_cache_service as cache
from core.services import image_upload_service as upload
from core.services.system_status_service import build_system_status


def test_public_url_uses_supabase_storage_not_github():
    with mock.patch.object(cache, "SUPABASE_URL", "https://project.supabase.co"):
        assert cache.get_image_url("mahabucha", "A 1.webp") == (
            "https://project.supabase.co/storage/v1/object/public/portfolio/"
            "image-library/mahabucha/A%201.webp"
        )


def test_update_file_list_reads_the_library_prefix():
    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"id": "id", "name": "269AA01.webp", "metadata": {"size": 42}}]
    with mock.patch.object(cache, "SUPABASE_URL", "https://project.supabase.co"), \
         mock.patch.object(cache, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.post", return_value=response) as post:
        cache.update_file_list()
    assert cache.CACHED_FILES["mahabucha"]["269aa01"] == "269AA01.webp"
    assert post.call_args_list[0].kwargs["json"]["prefix"] == "image-library/mahabucha"


def test_upload_raw_images_writes_to_supabase_storage():
    response = mock.Mock(status_code=201, text="")
    with mock.patch.object(upload, "SUPABASE_URL", "https://project.supabase.co"), \
         mock.patch.object(upload, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.post", return_value=response) as post, \
         mock.patch.object(upload.threading, "Thread"):
        result = upload.upload_raw_images("muteteam", [{"filename": "A.webp", "data": "ZmFrZQ=="}])
    assert result["success"] is True
    assert "/storage/v1/object/portfolio/image-library/muteteam/A.webp" in post.call_args.args[0]


def test_delete_library_image_uses_supabase_storage():
    response = mock.Mock(status_code=200, text="")
    with mock.patch.object(upload, "SUPABASE_URL", "https://project.supabase.co"), \
         mock.patch.object(upload, "SUPABASE_KEY", "service-key"), \
         mock.patch("requests.delete", return_value=response) as delete, \
         mock.patch.object(upload.threading, "Thread"):
        result = upload.delete_image_file("mahabucha", "A.webp")
    assert result["success"] is True
    assert "/storage/v1/object/portfolio/image-library/mahabucha/A.webp" in delete.call_args.args[0]


def test_system_status_reports_only_supabase_storage():
    app = type("App", (), {"server_start_time": datetime.now()})()
    with mock.patch("core.services.system_status_service.check_database_health", return_value={"status": "ok", "latency_ms": 1, "total_bookings": 2}), \
         mock.patch("core.services.system_status_service.get_supabase_storage_stats", return_value=(3, 1024 * 1024)):
        result = build_system_status(app)
    assert result["storage"]["supabase"]["count"] == 3
    assert "github" not in result["storage"]
