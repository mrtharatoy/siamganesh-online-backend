"""
Shared pytest fixtures for testing app.py.

app.py is a single-file Flask app that, at *module import time*,
unconditionally:
  1. calls update_file_list(), which makes real HTTP requests to the
     GitHub API to sync the image cache, and
  2. starts a live APScheduler BackgroundScheduler with jobs (one of
     which is scheduled to fire "immediately" via next_run_time=now()).

Neither of those is safe or desirable to run for real during a test
suite (network calls, real background threads, live cron jobs hitting
Facebook/LINE/Gemini). This conftest neutralizes those specific side
effects for the *import itself* so that the rest of app.py's pure
helper functions can be exercised safely and deterministically, without
patching or changing any of app.py's actual logic.
"""
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# app.py lives at the repo root, one level up from tests/.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Deterministic env vars so module-level constants in app.py have known
# values during tests, and so functions that early-return when
# Supabase/Gemini aren't configured take their (side-effect-free)
# fallback paths instead of trying to hit real external services.
os.environ["MAHABUCHA_PAGE_ID"] = "1000000001"
os.environ["MAHABUCHA_TOKEN"] = "test-mahabucha-token"
os.environ["MUTETEAM_PAGE_ID"] = "2000000002"
os.environ["MUTETEAM_TOKEN"] = "test-muteteam-token"
os.environ["GEMINI_API_KEY"] = ""
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""
os.environ["VERIFY_TOKEN"] = "test-verify-token"
os.environ["ALLOWED_ORIGINS"] = "https://example.com"


@pytest.fixture(scope="session", autouse=True)
def _import_app_safely():
    """
    Imports app.py once for the whole test session with its
    module-level network call and scheduler start neutralized.
    """
    with mock.patch("requests.get", side_effect=RuntimeError("network disabled in tests")), \
         mock.patch("requests.post", side_effect=RuntimeError("network disabled in tests")), \
         mock.patch("apscheduler.schedulers.background.BackgroundScheduler.start", lambda self: None):
        import app  # noqa: F401  (import triggers app.py's module-level code once)
    yield


@pytest.fixture
def app_module():
    """Returns the already-imported app module for use in tests."""
    import app
    return app
