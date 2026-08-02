"""Read display-only page configuration for backend-originated messages.

The admin portal stores editable page labels in `system_settings` under
`page_configuration`.  Backend notifications use this small boundary instead
of duplicating display labels, while retaining the registry value as a safe
fallback during an outage or before the setting has been created.
"""
import requests

from config import SUPABASE_KEY, SUPABASE_URL
from core.owners import OWNERS


PAGE_CONFIGURATION_SETTING = "page_configuration"


def get_owner_page_configuration(owner):
    """Return the central label/enabled state with safe registry fallbacks."""
    fallback = OWNERS.get(owner).display_name if owner in OWNERS else owner
    result = {"label": fallback, "enabled": True}
    if not (SUPABASE_URL and SUPABASE_KEY):
        return result

    try:
        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        response = requests.get(
            f"{rest_base}/system_settings",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={"id": f"eq.{PAGE_CONFIGURATION_SETTING}", "select": "value"},
            timeout=5,
        )
        if response.status_code != 200:
            return result
        rows = response.json()
        configuration = rows[0].get("value", {}) if rows else {}
        configured = configuration.get(owner, {}) if isinstance(configuration, dict) else {}
        label = configured.get("label") if isinstance(configured, dict) else None
        if isinstance(label, str) and label.strip():
            result["label"] = label.strip()
        if isinstance(configured, dict) and isinstance(configured.get("enabled"), bool):
            result["enabled"] = configured["enabled"]
        return result
    except (requests.RequestException, ValueError, TypeError):
        return result


def get_owner_display_name(owner):
    """Return the centrally configured label, or the stable registry label."""
    return get_owner_page_configuration(owner)["label"]


def is_owner_enabled(owner):
    """Disabled pages must not produce scheduled automation messages."""
    return get_owner_page_configuration(owner)["enabled"]
