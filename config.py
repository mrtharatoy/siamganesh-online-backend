"""
Environment variable loading for the Flask app.

Extracted from app.py (SG-B-101) with zero behavior change: every
constant name, default value, and the CORS ALLOWED_ORIGINS
fallback/warning are exactly as they were before this file existed.
app.py imports these names directly so existing test patches like
`mock.patch.object(app_module, "GITHUB_TOKEN", ...)` keep working
unchanged (Python binds a fresh name in app.py's namespace on
`from config import GITHUB_TOKEN`, independent of this module).
"""
import os

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "mrtharatoy")
REPO_NAME       = os.getenv("REPO_NAME", "siamganesh-online-backend")
BRANCH          = os.getenv("BRANCH", "main")

MAHABUCHA_PAGE_ID = os.environ.get('MAHABUCHA_PAGE_ID')
MAHABUCHA_TOKEN   = os.environ.get('MAHABUCHA_TOKEN')
MUTETEAM_PAGE_ID  = os.environ.get('MUTETEAM_PAGE_ID')
MUTETEAM_TOKEN    = os.environ.get('MUTETEAM_TOKEN')
LAOS_PAGE_ID          = os.environ.get('LAOS_PAGE_ID')
LAOS_TOKEN            = os.environ.get('LAOS_TOKEN')
RATCHAPRASONG_PAGE_ID = os.environ.get('RATCHAPRASONG_PAGE_ID')
RATCHAPRASONG_TOKEN   = os.environ.get('RATCHAPRASONG_TOKEN')
VERIFY_TOKEN      = os.environ.get('VERIFY_TOKEN')
GITHUB_TOKEN      = os.environ.get('GITHUB_TOKEN')
GEMINI_API_KEY    = os.environ.get('GEMINI_API_KEY')
SUPABASE_URL      = os.environ.get('SUPABASE_URL')
SUPABASE_KEY      = os.environ.get('SUPABASE_KEY')

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA') or os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM  = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM') or os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_ACCESS_TOKEN_LAOS          = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_LAOS') or os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_ACCESS_TOKEN_RATCHAPRASONG = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_RATCHAPRASONG') or os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_GROUP_ID_MAHABUCHA   = os.environ.get('LINE_GROUP_ID_MAHABUCHA')
LINE_GROUP_ID_MUTETEAM    = os.environ.get('LINE_GROUP_ID_MUTETEAM')
# เพจลาว/ราชประสงค์ ใช้กลุ่ม LINE เดียวกับมหาบูชา (ตามที่ผู้ใช้ยืนยัน ไม่ต้องมี group id แยก)
# -- core/clients/line_client.py routes them straight to
# LINE_GROUP_ID_MAHABUCHA by name, so no separate constants are needed here.

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
