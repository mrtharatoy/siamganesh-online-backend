"""
Environment variable loading for the Flask app.

Extracted from app.py (SG-B-101) with zero behavior change: every
constant name, default value, and the CORS ALLOWED_ORIGINS
fallback/warning are exactly as they were before this file existed.
Image assets use Supabase Storage; GitHub configuration is intentionally
absent so this service cannot accidentally use a source-code repository as
file storage.
"""
import base64
import json
import os

SUPABASE_URL      = os.environ.get('SUPABASE_URL')
SUPABASE_KEY      = os.environ.get('SUPABASE_KEY')


def _decode_jwt_role(token):
    """Best-effort, unverified decode of a Supabase key's `role` claim.
    Used only for the startup diagnostic below -- never for authorization."""
    try:
        payload_segment = token.split('.')[1]
        padded = payload_segment + '=' * (-len(payload_segment) % 4)
        return json.loads(base64.urlsafe_b64decode(padded)).get('role')
    except Exception:
        return None


# system_settings/bookings/catalogs require the `authenticated` (or
# service_role, which bypasses RLS outright) Postgres role to SELECT -- see
# supabase/migrations/20260728220942_fix_rls_policies.sql in the frontend
# repo. A key of the wrong role doesn't error: every request still returns
# HTTP 200, just with an empty row array, indistinguishable from "no such
# row" to a naive caller. This silently broke every scheduled LINE job
# (daily/monthly summaries, print-queue digest, photo-delivery follow-up)
# because the deployed SUPABASE_KEY behaved like `anon`, not `service_role`
# -- caught here, loudly, at import time instead of re-diagnosing it from
# cron logs again.
if SUPABASE_KEY:
    _key_role = _decode_jwt_role(SUPABASE_KEY)
    if _key_role != 'service_role':
        print('\n'.join([
            '=' * 70,
            '⚠️⚠️⚠️  SUPABASE_KEY IS NOT A service_role KEY  ⚠️⚠️⚠️',
            f"Decoded role claim: {_key_role!r} (expected 'service_role').",
            'system_settings/bookings/catalogs require an authenticated or',
            'service_role Postgres role to read via RLS. Every request will',
            'still return HTTP 200, just with an EMPTY result -- silently',
            'skipping every scheduled LINE summary/notification.',
            'Fix: set SUPABASE_KEY to the service_role secret from Supabase',
            'Dashboard -> Settings -> API, in both this deploy\'s env vars',
            'AND the GitHub Actions repo secret used by cron.yml.',
            '=' * 70,
        ]))

# All 5 owners (mahabucha, muteteam, muteteam_ceremony, laos,
# ratchaprasong) now share a single LINE OA token and a single LINE
# group -- both sourced from mahabucha's own env vars (falling back to
# the old generic names for anyone who hasn't renamed their env vars
# yet). Messages differentiate the page by name in the text instead
# (see core/services/notification_service.py). Per-owner
# LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM/_LAOS/_RATCHAPRASONG and
# LINE_GROUP_ID_MUTETEAM no longer exist -- core/clients/line_client.py
# has nothing left to route per owner.
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA') or os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_GROUP_ID = os.environ.get('LINE_GROUP_ID_MAHABUCHA') or os.environ.get('LINE_GROUP_ID')

# จำกัดโดเมนที่อนุญาตให้เรียก API นี้ได้ ตั้งค่าผ่าน env var ALLOWED_ORIGINS
# (คั่นด้วยจุลภาค เช่น "https://siamganesh.com,https://admin.siamganesh.com")
#
# SG-H-100: fail-closed. Previously, an unset ALLOWED_ORIGINS silently
# fell back to "*" (every origin allowed) with just a printed warning —
# easy to miss in production logs, and the app would boot and serve
# traffic with CORS effectively disabled. Now the app refuses to start
# at all if this isn't configured, so a missing/misconfigured deploy
# env fails loudly instead of shipping an open CORS policy.
_allowed_origins_env = os.environ.get('ALLOWED_ORIGINS', '').strip()
if not _allowed_origins_env:
    raise RuntimeError(
        "ALLOWED_ORIGINS ไม่ได้ตั้งค่า — ต้องระบุโดเมนที่อนุญาตให้เรียก API นี้ได้ "
        "ก่อนเริ่มแอป (คั่นด้วยจุลภาค เช่น "
        "\"https://siamganesh.com,https://admin.siamganesh.com\"); "
        "ไม่ fallback เป็น \"*\" อีกต่อไปเพื่อไม่ให้ CORS เปิดรับทุกโดเมนโดยไม่ได้ตั้งใจ"
    )
# rstrip trailing "/" — browsers never include a trailing slash in the
# Origin header, so a misconfigured env var with one would silently
# block every real request's CORS check.
ALLOWED_ORIGINS = [o.strip().rstrip('/') for o in _allowed_origins_env.split(',') if o.strip()]
