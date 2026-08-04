"""Read-only access to the admin portal's per-owner price tiers.

The admin portal stores price tiers (name, price, code prefix, and for the
laos page, LAK conversion inputs) in `system_settings` under `tray_pricing`,
keyed by owner. Backend LINE digests/summaries use this to group bookings by
tier name instead of by raw `total_price` -- important once a tier's price
can vary day-to-day (see the laos LAK-conversion feature), since grouping by
the exact price number would otherwise fragment into one bucket per booking.
"""
import requests

from config import SUPABASE_KEY, SUPABASE_URL

TRAY_PRICING_SETTING = "tray_pricing"


def get_tier_name_map(owner):
    """Returns {tier_id: tier_name} for one owner, or {} on any failure."""
    if not (SUPABASE_URL and SUPABASE_KEY):
        return {}

    try:
        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        response = requests.get(
            f"{rest_base}/system_settings",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            params={"id": f"eq.{TRAY_PRICING_SETTING}", "select": "value"},
            timeout=5,
        )
        if response.status_code != 200:
            return {}
        rows = response.json()
        tray_pricing = rows[0].get("value", {}) if rows else {}
        tiers = tray_pricing.get(owner) if isinstance(tray_pricing, dict) else None
        if not isinstance(tiers, list):
            return {}
        return {tier["id"]: tier["name"] for tier in tiers if isinstance(tier, dict) and tier.get("id") and tier.get("name")}
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return {}


def resolve_price_label(tier_map, booking):
    """Best-effort label for one booking's tier: the tier name if its
    `price_id` is still a known tier, else a formatted raw price, else
    'ไม่ระบุราคา'. Covers legacy bookings from before `price_id` was stored
    on every tray_item, and bookings whose tier was since deleted."""
    tray_items = booking.get("tray_items") or []
    price_id = tray_items[0].get("price_id") if tray_items and isinstance(tray_items[0], dict) else None
    if price_id and price_id in tier_map:
        return tier_map[price_id]
    price = booking.get("total_price")
    return "ไม่ระบุราคา" if price is None else f"฿{float(price):,.0f}"
