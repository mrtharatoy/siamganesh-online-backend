"""
Notifications blueprint (SG-B-104), extracted from app.py:
`/api/line-quota`, `/api/line-webhook`, `/api/notify-photo`.
Route logic is unchanged from the original app.py handlers of the same
name -- only the import source moved (LINE client logic already
extracted to core/clients/line_client.py since it's shared with
app.py's scheduler functions).

Dropped: app.py had a SECOND `/api/line-quota` GET handler
(`get_line_quota`, taking an `?owner=` query param) registered further
down the file. Confirmed via API_BASELINE.md (SG-000) and a live
production curl comparison that Werkzeug's URL map always matches the
FIRST-registered rule for an identical path+method pair -- so that
second handler was provably unreachable dead code in every version of
this app, not a behavior change introduced by this move. Only the
active handler (this file's line_quota) was carried over.
"""
from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from core.clients.line_client import get_line_token, fetch_quota
from core.schemas import NotifyPhotoBody
from core.services.notification_service import notify_print_queue

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.route('/api/line-quota', methods=['GET'])
def line_quota():
    return jsonify({
        "muteteam": fetch_quota(get_line_token('muteteam')),
        "mahabucha": fetch_quota(get_line_token('mahabucha'))
    }), 200


@notifications_bp.route('/api/line-webhook', methods=['POST'])
def line_webhook():
    try:
        # รับข้อมูลมาเฉยๆ ไม่ต้องปริ้น log แล้ว ป้องกัน log เต็ม
        body = request.get_json()
        return "OK", 200
    except Exception as e:
        print(f"Error handling LINE webhook: {e}")
        return "Error", 500


@notifications_bp.route('/api/notify-photo', methods=['POST'])
def notify_photo():
    data = request.json
    try:
        validated = NotifyPhotoBody(**data)
    except ValidationError:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบถ้วน"}), 400

    success, err_msg = notify_print_queue(
        validated.owner, validated.booking_code,
        person1_name=validated.person1_name,
        person2_name=validated.person2_name,
        customer_name=validated.customer_name,
        tray_count=validated.tray_count,
    )
    if not success:
        return jsonify({"success": False, "error": err_msg}), 200
    return jsonify({"success": True}), 200
