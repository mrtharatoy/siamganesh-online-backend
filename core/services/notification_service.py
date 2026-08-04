"""
Print-queue LINE notification message building. The 16:00 scheduler
runs only on the day before and the day of a ceremony, and reports the
bookings still waiting to print for that ceremony at that moment.
"""
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from core.clients.line_client import send_line_notification
from core.services.page_configuration_service import get_owner_display_name

MONTHS_TH = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]


def format_thai_date(value):
    """Renders every LINE notification date in one Thai short-date form."""
    return f"{value.day} {MONTHS_TH[value.month]} {value.year + 543}"


def booking_display_name(person1_name=None, person2_name=None, customer_name=None):
    """Same name-fallback used by the old per-booking notify: both
    person names if present, else person1, else customer_name, else a
    generic label."""
    if person1_name and person2_name:
        return f"{person1_name} และ {person2_name}"
    return person1_name or customer_name or 'ไม่ระบุชื่อ'


def _build_print_queue_digest_message(owner, items, ceremony_names=None):
    """items: current list of bookings in ``waiting_print`` for owner, each
    with a pre-resolved ``price_label`` (tier name, or a formatted raw price
    for bookings whose tier can't be resolved) -- resolving that label
    requires reading `tray_pricing`, which this module deliberately has no
    Supabase access to do itself; see core/services/pricing_service.py."""
    now_th = datetime.now(timezone(timedelta(hours=7)))
    date_str = format_thai_date(now_th)

    page_name = get_owner_display_name(owner)
    ceremony_label = " / ".join(ceremony_names or []) or "ไม่ระบุงานพิธี"
    lines = [
        "🖨️ [แจ้งเตือนคิวค้างปริ้น]",
        f"เพจ: {page_name}",
        f"งานพิธี: {ceremony_label}",
        f"วันที่: {date_str}",
    ]

    if not items:
        lines.extend([
            "สถานะ: ไม่มีรายการค้างปริ้น",
            "ตรวจสอบแล้ว ไม่มีรายการที่ต้องปริ้นในขณะนี้",
        ])
        return "\n".join(lines)

    lines.extend([
        "สถานะ: มีรายการค้างปริ้น",
    ])
    count_by_label = defaultdict(int)
    for item in items:
        count_by_label[item.get("price_label") or "ไม่ระบุราคา"] += 1
    for price_label, count in sorted(count_by_label.items()):
        # "ใบ" matches the unit an operator must physically print, and
        # keeps the digest useful even when several bookings share a tier.
        lines.append(f"- ราคา {price_label} จำนวน {count} ใบ")

    return "\n".join(lines)


def send_print_queue_digest(owner, items, *, ceremony_names=None, send_empty=False):
    """Sends the current print backlog for an owner.

    Empty queues normally stay quiet; the ceremony scheduler passes
    ``send_empty`` on both scheduled reporting days so the LINE group
    receives an explicit confirmation that there is nothing left to print.
    """
    if not items and not send_empty:
        return True, None
    text = _build_print_queue_digest_message(owner, items, ceremony_names)
    return send_line_notification(owner, text)
