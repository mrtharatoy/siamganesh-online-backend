"""
Shared GitHub-backed image cache, extracted from app.py (SG-B-103a,
a prerequisite slice of SG-B-103/SG-B-200 pulled forward because the
messenger/images/search route logic all read and refresh this same
cache -- extracting any one of those blueprints first requires this
module to exist without a circular import back to app.py).

`is_loaded()` / `get_last_refresh()` / `touch_last_refresh()` are
plain functions, not module-level bool/float names re-exported via
`from ... import NAME`. That distinction matters: a bare
`from core.services.image_cache_service import FILES_LOADED` in
another module would copy the *value* at import time, and this
module's own `_files_loaded = True` reassignment afterwards would
never be visible through that other module's stale copy. Functions
always look up the current value, so callers stay correct regardless
of which module calls them from.

`CACHED_FILES` / `TOTAL_IMAGES_SIZE` / `lock` remain plain module-level
names that ARE safe to import directly elsewhere: update_file_list()
mutates the two dicts in place (assigns into existing keys, never
rebinds the name), and `lock` is a single `threading.Lock()` object
whose identity -- not a copied value -- is what every caller needs to
share.

Every call site that used to do `LAST_CACHE_REFRESH = time.time()`
itself, immediately after calling update_file_list() under the lock,
must now call `touch_last_refresh()` at that exact same point instead
-- update_file_list() intentionally does NOT set this itself, exactly
matching the original app.py control flow where the caller (not
update_file_list) owned that timestamp.
"""
import threading
import time

import requests

from config import GITHUB_USERNAME, REPO_NAME, BRANCH, GITHUB_TOKEN

CACHED_FILES = {"mahabucha": {}, "muteteam": {}, "muteteam_ceremony": {}}
TOTAL_IMAGES_SIZE = {"mahabucha": 0, "muteteam": 0, "muteteam_ceremony": 0}
lock = threading.Lock()

_files_loaded = False
_last_cache_refresh = 0


def is_loaded():
    return _files_loaded


def get_last_refresh():
    return _last_cache_refresh


def touch_last_refresh():
    global _last_cache_refresh
    _last_cache_refresh = time.time()


def update_file_list():
    global _files_loaded
    print("[SYNC] Updating image list from GitHub...")
    headers = {
        "User-Agent": "Siamganesh-Bot",
        "Accept": "application/vnd.github.v3+json",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    for page in ["mahabucha", "muteteam", "muteteam_ceremony"]:
        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/images/{page}?ref={BRANCH}&t={int(time.time())}"
        try:
            r = requests.get(api_url, headers=headers, timeout=15)
            if r.status_code == 200:
                files = r.json()
                temp_cache = {}
                total_size = 0
                for item in files:
                    if item['type'] == 'file' and item['name'] != '.keep':
                        name_no_ext = item['name'].rsplit('.', 1)[0].strip().lower()
                        temp_cache[name_no_ext] = item['name']
                        total_size += item.get('size', 0)
                CACHED_FILES[page] = temp_cache
                TOTAL_IMAGES_SIZE[page] = total_size
                print(f"✅ {page.upper()} loaded: {len(temp_cache)} images, Size: {total_size} bytes.")
        except Exception as e:
            print(f"❌ Error {page}: {e}")
    _files_loaded = True


def get_image_url(page, filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/images/{page}/{filename}"
