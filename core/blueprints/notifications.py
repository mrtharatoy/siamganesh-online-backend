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
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify

from core.clients.line_client import get_line_token, send_line_notification, fetch_quota

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
    owner = data.get('owner')
    booking_code = data.get('booking_code')

    person1_name = data.get('person1_name')
    person2_name = data.get('person2_name')
    customer_name = data.get('customer_name')

    if person1_name and person2_name:
        display_name = f"{person1_name} และ {person2_name}"
    else:
        display_name = person1_name or customer_name or 'ไม่ระบุชื่อ'

    tray_count = data.get('tray_count', 0)

    if not owner or not booking_code:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบถ้วน"}), 400

    now_th = datetime.now(timezone(timedelta(hours=7)))
    months_th = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    date_str = f"{now_th.day} {months_th[now_th.month]} {now_th.year + 543} เวลา {now_th.strftime('%H:%M')} น."

    page_name = "มหาบูชา" if owner == "mahabucha" else ("มูเตทีม (งานพิธี)" if owner == "muteteam_ceremony" else "มูเตทีม")
    text = (
        f"🔔 [คิวปริ้นใหม่]\n"
        f"เพจ: {page_name}\n"
        f"วันที่: {date_str}\n"
        f"รหัสจอง: {booking_code}\n"
        f"ลูกค้า: {display_name}"
    )

    if owner not in ["mahabucha", "muteteam_ceremony"]:
        text += f"\nจำนวน: {tray_count} องค์เทพ"

    success, err_msg = send_line_notification(owner, text)
    if not success:
        return jsonify({"success": False, "error": err_msg}), 200
    return jsonify({"success": True}), 200
