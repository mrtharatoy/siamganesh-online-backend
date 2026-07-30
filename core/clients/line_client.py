"""
LINE Notify Messaging API client, extracted from app.py (SG-B-104).

All 5 owners now share a single LINE channel token and a single LINE
group (SG-B-2xx: consolidated off of mahabucha's own credentials) --
the `owner` parameter is kept on send_line_notification purely so
call sites don't need to change, and so the log line still says which
owner's message failed/succeeded; it no longer selects a
token/group. Messages differentiate the page by name in their own
text (core/services/notification_service.py builds that).

Used by the notifications blueprint (core/blueprints/notifications.py)
and by app.py's own scheduler functions (mahabucha_daily_summary,
muteteam_ceremony_daily_summary, muteteam_monthly_summary, and the
per-owner print-queue digest), which is why this lives in a shared
client module rather than inside the blueprint itself.
"""
import requests

from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_GROUP_ID


def send_line_notification(owner, text):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print(f"❌ [LINE] Missing LINE_CHANNEL_ACCESS_TOKEN (sending for {owner})")
        return False, "Missing LINE_CHANNEL_ACCESS_TOKEN"

    if not LINE_GROUP_ID:
        print(f"❌ [LINE] Missing LINE_GROUP_ID (sending for {owner})")
        return False, "Missing LINE_GROUP_ID"

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "to": LINE_GROUP_ID,
        "messages": [{"type": "text", "text": text}]
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            print(f"✅ [LINE] Notification sent for {owner}.")
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
