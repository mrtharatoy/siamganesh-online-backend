"""
LINE Notify Messaging API client, extracted from app.py (SG-B-104).
Logic unchanged from the original app.py functions of the same name --
only the import source for LINE config moved.

Used by the notifications blueprint (core/blueprints/notifications.py)
and by app.py's own scheduler functions (check_trending_news,
mahabucha_daily_summary, muteteam_ceremony_daily_summary,
muteteam_monthly_summary), which is why this lives in a shared client
module rather than inside the blueprint itself.
"""
import requests

from config import (
    LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA,
    LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM, LINE_CHANNEL_ACCESS_TOKEN_LAOS,
    LINE_CHANNEL_ACCESS_TOKEN_RATCHAPRASONG,
    LINE_GROUP_ID_MAHABUCHA, LINE_GROUP_ID_MUTETEAM,
)

# owner -> the *name* of this module's own token/group constant (not its
# value), so a test's mock.patch.object(line_client, "LINE_..._X", ...)
# is picked up via globals() at call time exactly like the plain
# module-level names it replaces.
_TOKEN_ATTR_BY_OWNER = {
    "mahabucha": "LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA",
    "muteteam": "LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM",
    "muteteam_ceremony": "LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM",
    "laos": "LINE_CHANNEL_ACCESS_TOKEN_LAOS",
    "ratchaprasong": "LINE_CHANNEL_ACCESS_TOKEN_RATCHAPRASONG",
}
# laos/ratchaprasong intentionally reuse mahabucha's LINE group (no
# separate group was provisioned for them -- confirmed by the user).
_GROUP_ATTR_BY_OWNER = {
    "mahabucha": "LINE_GROUP_ID_MAHABUCHA",
    "muteteam": "LINE_GROUP_ID_MUTETEAM",
    "muteteam_ceremony": "LINE_GROUP_ID_MUTETEAM",
    "laos": "LINE_GROUP_ID_MAHABUCHA",
    "ratchaprasong": "LINE_GROUP_ID_MAHABUCHA",
}


def get_line_token(owner):
    attr = _TOKEN_ATTR_BY_OWNER.get(owner)
    token = globals().get(attr) if attr else None
    return token or LINE_CHANNEL_ACCESS_TOKEN


def send_line_notification(owner, text):
    token = get_line_token(owner)
    if not token:
        print(f"❌ [LINE] Missing LINE_CHANNEL_ACCESS_TOKEN for {owner}")
        return False, f"Missing LINE_CHANNEL_ACCESS_TOKEN for {owner}"

    group_attr = _GROUP_ATTR_BY_OWNER.get(owner, "LINE_GROUP_ID_MUTETEAM")
    group_id = globals().get(group_attr)
    if not group_id:
        print(f"❌ [LINE] Missing Group ID for owner: {owner}")
        return False, f"Missing Group ID for owner: {owner}"

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    data = {
        "to": group_id,
        "messages": [{"type": "text", "text": text}]
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            print(f"✅ [LINE] Notification sent to {owner} group.")
            return True, None
        else:
            print(f"❌ [LINE] Failed to send: {r.status_code} {r.text}")
            return False, f"LINE API Error {r.status_code}: {r.text}"
    except Exception as e:
        print(f"❌ [LINE] Error sending notification: {e}")
        return False, str(e)


def fetch_quota(token):
    """Message quota usage/limit for a single channel token, or None if
    no token or the LINE API call fails. Used by GET /api/line-quota."""
    if not token:
        return None
    try:
        h = {"Authorization": f"Bearer {token}"}
        usage_res = requests.get("https://api.line.me/v2/bot/message/quota/consumption", headers=h, timeout=5)
        limit_res = requests.get("https://api.line.me/v2/bot/message/quota", headers=h, timeout=5)

        usage = usage_res.json().get('totalUsage', 0) if usage_res.status_code == 200 else 0
        limit_data = limit_res.json() if limit_res.status_code == 200 else {}
        limit = limit_data.get('value', 0)

        return {"usage": usage, "limit": limit}
    except:
        return None
