"""Minimal client for Supabase REST calls used by HTTP-facing debug routes."""
import requests


def upsert_debug_webhook(supabase_url, supabase_key, event, occurred_at):
    base = supabase_url.rstrip("/")
    url = f"{base}/system_settings" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    payload = {"id": "debug_webhook", "value": {"event": event, "time": occurred_at}}
    return requests.post(url, headers=headers, json=payload, timeout=5)


def get_debug_webhook(supabase_url, supabase_key):
    base = supabase_url.rstrip("/")
    url = f"{base}/system_settings?id=eq.debug_webhook" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings?id=eq.debug_webhook"
    headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
    return requests.get(url, headers=headers)
