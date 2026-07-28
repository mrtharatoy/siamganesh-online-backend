"""
SG-H-100: config.py must fail closed on ALLOWED_ORIGINS instead of
silently falling back to "*" (every origin allowed).

config.py runs its ALLOWED_ORIGINS validation at *module import time*,
so these tests reload it fresh under a controlled environment rather
than using the already-imported module from conftest.py's app fixture
(which was imported once, at session start, with ALLOWED_ORIGINS
already set to a valid value and must stay that way for every other
test in the suite).
"""
import importlib
import os
from contextlib import contextmanager

import pytest

import config as config_module


@contextmanager
def _config_reloaded_with_env(allowed_origins_value):
    """Reload config.py with ALLOWED_ORIGINS set to the given value (or
    removed entirely if None) for the duration of the `with` block,
    restoring the real module and env var afterwards so other tests
    keep seeing the original, valid config."""
    original_env = os.environ.get("ALLOWED_ORIGINS")
    try:
        if allowed_origins_value is None:
            os.environ.pop("ALLOWED_ORIGINS", None)
        else:
            os.environ["ALLOWED_ORIGINS"] = allowed_origins_value
        importlib.reload(config_module)
        yield config_module
    finally:
        if original_env is None:
            os.environ.pop("ALLOWED_ORIGINS", None)
        else:
            os.environ["ALLOWED_ORIGINS"] = original_env
        importlib.reload(config_module)


def test_config_import_raises_when_allowed_origins_unset():
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        with _config_reloaded_with_env(None):
            pass


def test_config_import_raises_when_allowed_origins_blank():
    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        with _config_reloaded_with_env("   "):
            pass


def test_config_parses_comma_separated_origins_and_strips_trailing_slash():
    with _config_reloaded_with_env("https://siamganesh.com/,https://admin.siamganesh.com") as reloaded:
        assert reloaded.ALLOWED_ORIGINS == [
            "https://siamganesh.com",
            "https://admin.siamganesh.com",
        ]


def test_config_module_is_restored_to_the_real_test_env_value_after_reload(app_module):
    # Sanity check that the reload dance above doesn't leak a broken
    # config module into the rest of the suite: app.py's already-bound
    # ALLOWED_ORIGINS name (captured at its own import time) is
    # untouched by any of the config reloads above.
    assert config_module.ALLOWED_ORIGINS == ["https://example.com"]
