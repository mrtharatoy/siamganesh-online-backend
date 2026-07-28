"""
Print-queue LINE notification message building (SG-B-202), extracted
from core/blueprints/notifications.py's notify_photo() so the route
becomes parse-request/call-service/map-response. Logic unchanged,
including the Thai date formatting and the owner-conditional
tray_count line.
"""
from datetime import datetime, timezone, timedelta

from core.clients.line_client import send_line_notification
from core.owners import OWNERS

MONTHS_TH = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def _build_print_queue_message(owner, booking_code, display_name, tray_count):
    now_th = datetime.now(timezone(timedelta(hours=7)))
    date_str = f"{now_th.day} {MONTHS_TH[now_th.month]} {now_th.year + 543} เวลา {now_th.strftime('%H:%M')} น."

    known = OWNERS.get(owner)
    page_name = known.display_name if known else "มูเตทีม"
    text = (
        f"🔔 [คิวปริ้นใหม่]\n"
        f"เพจ: {page_name}\n"
        f"วันที่: {date_str}\n"
        f"รหัสจอง: {booking_code}\n"
        f"ลูกค้า: {display_name}"
    )

    if not known or known.style != "mahabucha":
        text += f"\nจำนวน: {tray_count} องค์เทพ"

    return text


def notify_print_queue(owner, booking_code, person1_name=None, person2_name=None, customer_name=None, tray_count=0):
    """Sends the "new print queue item" LINE notification. Returns
    (success, error_message_or_None), matching send_line_notification's
    own return shape."""
    if person1_name and person2_name:
        display_name = f"{person1_name} และ {person2_name}"
    else:
        display_name = person1_name or customer_name or 'ไม่ระบุชื่อ'

    text = _build_print_queue_message(owner, booking_code, display_name, tray_count)
    return send_line_notification(owner, text)
