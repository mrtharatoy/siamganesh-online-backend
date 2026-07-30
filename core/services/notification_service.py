"""
Print-queue LINE notification message building (SG-B-202 original;
SG-B-2xx replaced the instant per-booking push with a once-daily
16:00 digest per owner -- app.py's *_print_queue_digest scheduler jobs
query the day's new/queued bookings and call send_print_queue_digest
once per owner with the whole list, instead of calling
send_line_notification once per booking as it used to).
"""
from datetime import datetime, timezone, timedelta

from core.clients.line_client import send_line_notification
from core.owners import OWNERS

MONTHS_TH = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def booking_display_name(person1_name=None, person2_name=None, customer_name=None):
    """Same name-fallback used by the old per-booking notify: both
    person names if present, else person1, else customer_name, else a
    generic label."""
    if person1_name and person2_name:
        return f"{person1_name} และ {person2_name}"
    return person1_name or customer_name or 'ไม่ระบุชื่อ'


def _build_print_queue_digest_message(owner, items):
    """items: list of {booking_code, display_name, tray_count}, already
    filtered to "created today or moved to waiting_print today" for
    this owner by the caller."""
    now_th = datetime.now(timezone(timedelta(hours=7)))
    date_str = f"{now_th.day} {MONTHS_TH[now_th.month]} {now_th.year + 543}"

    known = OWNERS.get(owner)
    page_name = known.display_name if known else owner
    include_tray_count = not known or known.style != "mahabucha"

    lines = [
        "🔔 [สรุปคิวปริ้นประจำวัน]",
        f"เพจ: {page_name}",
        f"วันที่: {date_str}",
        f"จำนวนรายการวันนี้: {len(items)} รายการ",
        "",
    ]
    for i, item in enumerate(items, start=1):
        line = f"{i}. {item['booking_code']} - {item['display_name']}"
        if include_tray_count:
            line += f" ({item['tray_count']} องค์เทพ)"
        lines.append(line)

    return "\n".join(lines)


def send_print_queue_digest(owner, items):
    """Sends one combined "print queue" LINE message summarizing every
    booking in `items` for this owner today. No-op (returns (True,
    None) without sending) when `items` is empty -- callers should
    generally skip the call in that case too, but this guards
    defensively against an accidental empty-list send."""
    if not items:
        return True, None
    text = _build_print_queue_digest_message(owner, items)
    return send_line_notification(owner, text)
