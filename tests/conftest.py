"""
Shared pytest fixtures for testing app.py.

app.py is a single-file Flask app that, at *module import time*,
unconditionally calls update_file_list(), which makes real HTTP requests
to the GitHub API to sync the image cache.

That isn't safe or desirable to run for real during a test suite
(network calls hitting a real external service). This conftest
neutralizes that specific side effect for the *import itself* so that
the rest of app.py's pure helper functions can be exercised safely and
deterministically, without patching or changing any of app.py's actual
logic. (Scheduled jobs -- previously a live APScheduler
BackgroundScheduler started at import time -- now run out-of-process via
Render Cron Jobs invoking cron_jobs.py, so there's no scheduler start to
neutralize here anymore.)
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
# Supabase isn't configured take their (side-effect-free)
# fallback paths instead of trying to hit real external services.
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""
os.environ["ALLOWED_ORIGINS"] = "https://example.com"


@pytest.fixture(scope="session", autouse=True)
def _import_app_safely():
    """
    Imports app.py once for the whole test session with its
    module-level network call neutralized.
    """
    with mock.patch("requests.get", side_effect=RuntimeError("network disabled in tests")), \
         mock.patch("requests.post", side_effect=RuntimeError("network disabled in tests")):
        import app  # noqa: F401  (import triggers app.py's module-level code once)
    yield


@pytest.fixture
def app_module():
    """Returns the already-imported app module for use in tests."""
    import app
    return app
