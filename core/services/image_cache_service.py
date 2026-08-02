"""Supabase Storage-backed index for the admin image library.

Runtime image storage deliberately lives under
``portfolio/image-library/<owner>/``.  GitHub is no longer queried or used
as a CDN; the small in-memory index only avoids repeatedly listing Storage.
"""
import time
import threading
from urllib.parse import quote

import requests

from config import SUPABASE_URL, SUPABASE_KEY
from core.owners import PAGE_OWNERS

BUCKET = "portfolio"
LIBRARY_PREFIX = "image-library"
CACHED_FILES = {owner: {} for owner in PAGE_OWNERS}
TOTAL_IMAGES_SIZE = {owner: 0 for owner in PAGE_OWNERS}
lock = threading.Lock()
_files_loaded = False
_last_cache_refresh = 0


def is_loaded(): return _files_loaded
def get_last_refresh(): return _last_cache_refresh
def touch_last_refresh():
    global _last_cache_refresh
    _last_cache_refresh = time.time()


def _headers():
    return {"apikey": SUPABASE_KEY or "", "Authorization": f"Bearer {SUPABASE_KEY or ''}"}


def _folder(owner): return f"{LIBRARY_PREFIX}/{owner}"


def update_file_list():
    global _files_loaded
    if not (SUPABASE_URL and SUPABASE_KEY):
        print("❌ Supabase Storage is not configured")
        return
    print("[SYNC] Updating image list from Supabase Storage...")
    base = SUPABASE_URL.rstrip("/")
    for owner in PAGE_OWNERS:
        try:
            response = requests.post(
                f"{base}/storage/v1/object/list/{BUCKET}", headers=_headers(),
                json={"prefix": _folder(owner), "limit": 1000, "offset": 0}, timeout=15,
            )
            response.raise_for_status()
            files = response.json()
            cache, total_size = {}, 0
            for item in files:
                if item.get("id") is None:
                    continue
                filename = item.get("name", "")
                if not filename:
                    continue
                cache[filename.rsplit(".", 1)[0].strip().lower()] = filename
                total_size += item.get("metadata", {}).get("size", 0)
            CACHED_FILES[owner] = cache
            TOTAL_IMAGES_SIZE[owner] = total_size
            print(f"✅ {owner.upper()} loaded: {len(cache)} images, Size: {total_size} bytes.")
        except Exception as exc:
            print(f"❌ Error {owner}: {exc}")
    _files_loaded = True


def get_image_url(owner, filename):
    path = quote(f"{_folder(owner)}/{filename}")
    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{BUCKET}/{path}"


def remove_cached_file(owner, filename):
    """Remove one library entry immediately after a successful/idempotent delete.

    Storage listing refreshes run in the background, so relying only on the
    refresh could briefly return a just-deleted filename to the admin UI.
    """
    key = filename.rsplit(".", 1)[0].strip().lower()
    CACHED_FILES.get(owner, {}).pop(key, None)
