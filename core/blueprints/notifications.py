"""
Notifications blueprint (SG-B-104), extracted from app.py:
`/api/line-quota`, `/api/line-webhook`.

Dropped: app.py had a SECOND `/api/line-quota` GET handler
(`get_line_quota`, taking an `?owner=` query param) registered further
down the file. Confirmed via API_BASELINE.md (SG-000) and a live
production curl comparison that Werkzeug's URL map always matches the
FIRST-registered rule for an identical path+method pair -- so that
second handler was provably unreachable dead code in every version of
this app, not a behavior change introduced by this move. Only the
active handler (this file's line_quota) was carried over.

`/api/notify-photo` (the immediate per-booking LINE notification) was
removed in the SG-B-2xx LINE consolidation: the frontend no longer
calls it -- print-queue notifications are now a once-daily 16:00
digest per owner (see app.py's *_print_queue_digest scheduler jobs),
not an instant push per booking. notify_print_queue/NotifyPhotoBody
have no remaining callers and were deleted with it.

`/api/line-quota` now reports one shared quota (all 5 owners share a
single LINE channel token as of the same consolidation), instead of
separate muteteam/mahabucha numbers for what is now the same channel.
"""
from flask import Blueprint, request, jsonify

from core.clients import line_client

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route('/api/line-quota', methods=['GET'])
def line_quota():
    # Read line_client's own module attribute (not a direct `from
    # config import ...`) so tests can mock.patch.object(line_client,
    # "LINE_CHANNEL_ACCESS_TOKEN", ...) same as every other LINE test.
    return jsonify({"quota": line_client.fetch_quota(line_client.LINE_CHANNEL_ACCESS_TOKEN)}), 200


@notifications_bp.route('/api/line-webhook', methods=['POST'])
def line_webhook():
    try:
        # รับข้อมูลมาเฉยๆ ไม่ต้องปริ้น log แล้ว ป้องกัน log เต็ม
        body = request.get_json()
        return "OK", 200
    except Exception as e:
        print(f"Error handling LINE webhook: {e}")
        return "Error", 500
