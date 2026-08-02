import os
import re
import json
import threading
import requests
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import (
    SUPABASE_URL, SUPABASE_KEY, ALLOWED_ORIGINS,
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# Read by system_status via flask.current_app (core/blueprints/system.py,
# SG-B-106) rather than a direct import, to avoid a circular import.
app.server_start_time = datetime.now()

# --- Centralized error handlers (SG-B-107) ---
from core.errors import register_error_handlers
register_error_handlers(app)

# --- [FILE] 2. SUPABASE STORAGE IMAGE INDEX (core/services/image_cache_service.py) ---
# CACHED_FILES/TOTAL_IMAGES_SIZE/lock/is_loaded/get_image_url have no
# remaining direct callers in app.py now that the images (SG-B-103) and
# system (SG-B-106) blueprints own every call site that needed them.
# update_file_list() is still called once below to warm the cache at
# process startup, exactly as before.
from core.services.image_cache_service import update_file_list


# --- [FILE] 6.5 / 7 / 8 / 8.5 / 9 IMAGES API (moved to core/blueprints/images.py, SG-B-103) ---
from core.blueprints.images import images_bp
app.register_blueprint(images_bp)

# --- [NOTIFY] 11. LINE NOTIFICATIONS (moved to core/blueprints/notifications.py, SG-B-104) ---
# send_line_notification is still used by the scheduler functions below
# (mahabucha_daily_summary, muteteam_ceremony_daily_summary,
# muteteam_monthly_summary); send_print_queue_digest backs the daily
# current print-backlog jobs.
from core.clients.line_client import send_line_notification
from core.services.notification_service import format_thai_date, send_print_queue_digest
from core.owners import OWNERS
from core.blueprints.notifications import notifications_bp
app.register_blueprint(notifications_bp)

# --- [SEARCH] 6 / [SYSTEM] SYSTEM STATUS (moved to core/blueprints/system.py, SG-B-106) ---
from core.blueprints.system import system_bp
app.register_blueprint(system_bp)

update_file_list()

# Four ceremony pages move a booking to `ready_to_send` after its photos are
# prepared.  This follow-up deliberately excludes muteteam (daily), whose
# work is not tied to a single ceremony date.
PHOTO_DELIVERY_FOLLOWUP_OWNERS = (
    "mahabucha", "muteteam_ceremony", "laos", "ratchaprasong",
)
PHOTO_DELIVERY_FOLLOWUP_SETTING = "photo_delivery_followup"
PHOTO_DELIVERY_FOLLOWUP_STATE_SETTING = "photo_delivery_followup_state"


def _read_setting(rest_base, headers, setting_id):
    response = requests.get(
        f"{rest_base}/system_settings", headers=headers,
        params={"id": f"eq.{setting_id}", "select": "value"}, timeout=10,
    )
    if response.status_code != 200:
        return None
    rows = response.json()
    return rows[0].get("value", {}) if rows else {}


def _write_setting(rest_base, headers, setting_id, value):
    response = requests.post(
        f"{rest_base}/system_settings",
        headers={**headers, "Prefer": "resolution=merge-duplicates"},
        json={"id": setting_id, "value": value, "updated_at": datetime.now(timezone.utc).isoformat()},
        timeout=10,
    )
    return response.status_code in (200, 201)


def _format_ceremony_date(value):
    """Format a galleries.event_date without leaking an ISO date to LINE."""
    return format_thai_date(datetime.strptime(value, "%Y-%m-%d").date())


def _owner_photo_delivery_followup(owner):
    """At 21:00 after a ceremony, report the customers still awaiting photos.

    The state only records ceremonies that have actually had a pending queue.
    Therefore enabling this automation never produces completion spam for old
    ceremonies that were already finished before this feature existed.
    """
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return

        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        enabled_values = _read_setting(rest_base, headers, PHOTO_DELIVERY_FOLLOWUP_SETTING)
        if not isinstance(enabled_values, dict) or not enabled_values.get(owner, False):
            print(f"[TIMER] [PHOTO-FOLLOWUP] Disabled for {owner}.")
            return

        tz = timezone(timedelta(hours=7))
        today = datetime.now(tz).date()
        galleries_response = requests.get(
            f"{rest_base}/galleries", headers=headers,
            params={"owner": f"eq.{owner}", "event_date": f"lt.{today.isoformat()}", "select": "id,caption,event_date"},
            timeout=15,
        )
        if galleries_response.status_code != 200:
            return
        ceremonies = [gallery for gallery in galleries_response.json() if gallery.get("id") and gallery.get("event_date")]
        if not ceremonies:
            return

        ceremony_ids = {gallery["id"] for gallery in ceremonies}
        bookings_response = requests.get(
            f"{rest_base}/bookings", headers=headers,
            params={"owner": f"eq.{owner}", "status": "eq.ready_to_send", "select": "gallery_id"},
            timeout=15,
        )
        if bookings_response.status_code != 200:
            return

        pending_by_gallery = defaultdict(int)
        for booking in bookings_response.json():
            gallery_id = booking.get("gallery_id")
            if gallery_id in ceremony_ids:
                pending_by_gallery[gallery_id] += 1

        state_values = _read_setting(rest_base, headers, PHOTO_DELIVERY_FOLLOWUP_STATE_SETTING)
        if state_values is None:
            return
        state_values = state_values if isinstance(state_values, dict) else {}
        owner_state = state_values.get(owner, {}) if isinstance(state_values.get(owner, {}), dict) else {}
        tracked = set(owner_state.get("tracked_gallery_ids", []))
        completed = set(owner_state.get("completed_gallery_ids", []))

        pending_ceremonies = [gallery for gallery in ceremonies if pending_by_gallery.get(gallery["id"], 0)]
        newly_completed = [
            gallery for gallery in ceremonies
            if gallery["id"] in tracked and not pending_by_gallery.get(gallery["id"], 0) and gallery["id"] not in completed
        ]

        page_name = OWNERS.get(owner).display_name if owner in OWNERS else owner
        date_text = format_thai_date(today)
        if pending_ceremonies:
            lines = [
                "📦 [ติดตามคิวรอส่งภาพ]",
                f"เพจ: {page_name}",
                f"วันที่: {date_text}",
                "สถานะ: รอส่งภาพให้ลูกค้า",
            ]
            total = 0
            for gallery in pending_ceremonies:
                count = pending_by_gallery[gallery["id"]]
                total += count
                lines.append(f"- {gallery.get('caption') or 'ไม่ระบุงานพิธี'} (จัดพิธี {_format_ceremony_date(gallery['event_date'])}): {count} คน")
            lines.append(f"รวมค้างส่งภาพ {total} คน")
            send_line_notification(owner, "\n".join(lines))
            tracked.update(gallery["id"] for gallery in pending_ceremonies)
            completed.difference_update(gallery["id"] for gallery in pending_ceremonies)
            print(f"✅ [PHOTO-FOLLOWUP] Sent pending-photo report for {owner} ({total} คน)")

        if newly_completed:
            lines = [
                "✅ [ปิดคิวส่งภาพ]",
                f"เพจ: {page_name}",
                f"วันที่: {date_text}",
                "งานพิธีที่ส่งภาพครบแล้ว",
            ]
            for gallery in newly_completed:
                lines.append(f"- {gallery.get('caption') or 'ไม่ระบุงานพิธี'} (จัดพิธี {_format_ceremony_date(gallery['event_date'])})")
            lines.append("สถานะ: ส่งภาพให้ลูกค้าครบแล้ว")
            success, error = send_line_notification(owner, "\n".join(lines))
            if success:
                completed.update(gallery["id"] for gallery in newly_completed)
                print(f"✅ [PHOTO-FOLLOWUP] Sent completion report for {owner} ({len(newly_completed)} งาน)")
            else:
                print(f"❌ [PHOTO-FOLLOWUP] Failed completion report for {owner}: {error}")

        next_owner_state = {
            "tracked_gallery_ids": sorted(tracked),
            "completed_gallery_ids": sorted(completed),
        }
        if next_owner_state != owner_state:
            state_values[owner] = next_owner_state
            if not _write_setting(rest_base, headers, PHOTO_DELIVERY_FOLLOWUP_STATE_SETTING, state_values):
                print(f"❌ [PHOTO-FOLLOWUP] Could not persist follow-up state for {owner}.")

    except Exception as error:
        print(f"❌ [PHOTO-FOLLOWUP] Error for {owner}: {error}")


def mahabucha_photo_delivery_followup():
    _owner_photo_delivery_followup("mahabucha")


def muteteam_ceremony_photo_delivery_followup():
    _owner_photo_delivery_followup("muteteam_ceremony")


def laos_photo_delivery_followup():
    _owner_photo_delivery_followup("laos")


def ratchaprasong_photo_delivery_followup():
    _owner_photo_delivery_followup("ratchaprasong")

# --- [PRINT] 12. PRINT-QUEUE DIGEST SCHEDULER (SG-B-2xx) ---
# Replaces the old instant per-booking "notify-photo" push: each owner
# gets one 16:00 report of every code still in waiting_print. During a
# ceremony, an empty report is sent as an explicit "no pending print"
# confirmation. Parameterized for all five owners.
def _owner_print_queue_digest(owner):
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return

        print(f"[TIMER] [DIGEST] Running print-queue digest check for {owner}...")
        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

        # 1. Check if the digest is enabled for this owner. Reuses the
        # existing `line_notify_group` setting (same one the Settings
        # page's "แจ้งเตือน LINE [เพจ]" switches write) -- its meaning
        # just changed from "send instantly" to "include in the 16:00
        # digest". A legacy `{"enabled": bool}` shape (predating the
        # per-owner keys) is honored as a fallback for every owner.
        url_settings = f"{rest_base}/system_settings"
        res_settings = requests.get(url_settings, headers=headers, params={"id": "eq.line_notify_group", "select": "value"}, timeout=10)
        if res_settings.status_code != 200 or not res_settings.json():
            return

        setting_val = res_settings.json()[0].get("value", {})
        enabled = setting_val.get(owner)
        if enabled is None:
            enabled = setting_val.get("enabled", True)
        if not enabled:
            print(f"[TIMER] [DIGEST] Print-queue digest for {owner} is disabled.")
            return

        # 2. Fetch the current backlog. The LINE template groups it by the
        # price selected by customers rather than exposing individual codes.
        tz = timezone(timedelta(hours=7))
        today = datetime.now(tz).date()

        url_bookings = f"{rest_base}/bookings"
        res_bookings = requests.get(
            url_bookings, headers=headers,
            params={
                "owner": f"eq.{owner}",
                "status": "eq.waiting_print",
                "select": "gallery_id,total_price",
            },
            timeout=15,
        )
        if res_bookings.status_code != 200:
            return

        bookings = res_bookings.json()
        items = [{"total_price": b.get("total_price")} for b in bookings]

        # Gallery captions provide the ceremony context in the LINE template.
        # The same query determines whether an empty confirmation is useful:
        # a ceremony whose date has not passed is considered in progress by
        # the scheduler, matching the daily-summary workflow.
        res_galleries = requests.get(
            f"{rest_base}/galleries", headers=headers,
            params={"owner": f"eq.{owner}", "select": "id,caption,event_date"},
            timeout=10,
        )
        galleries = res_galleries.json() if res_galleries.status_code == 200 else []
        gallery_by_id = {gallery.get("id"): gallery for gallery in galleries}
        active_galleries = [
            gallery for gallery in galleries
            if gallery.get("event_date") and gallery["event_date"] >= today.isoformat()
        ]
        ceremony_names = list(dict.fromkeys(
            gallery_by_id.get(booking.get("gallery_id"), {}).get("caption")
            for booking in bookings
            if gallery_by_id.get(booking.get("gallery_id"), {}).get("caption")
        ))
        if not ceremony_names:
            ceremony_names = list(dict.fromkeys(
                gallery.get("caption") for gallery in active_galleries if gallery.get("caption")
            ))

        send_empty = not items and bool(active_galleries)
        if not items and not send_empty:
            print(f"[TIMER] [DIGEST] No print backlog or active ceremony for {owner}.")
            return

        success, err = send_print_queue_digest(
            owner, items, ceremony_names=ceremony_names, send_empty=send_empty,
        )
        if success:
            print(f"✅ [DIGEST] Sent print-queue digest for {owner} ({len(items)} รายการ)")
        else:
            print(f"❌ [DIGEST] Failed to send print-queue digest for {owner}: {err}")

    except Exception as e:
        print(f"❌ [DIGEST] Error in print-queue digest for {owner}: {e}")


def mahabucha_print_queue_digest():
    _owner_print_queue_digest("mahabucha")


def muteteam_print_queue_digest():
    _owner_print_queue_digest("muteteam")


def muteteam_ceremony_print_queue_digest():
    _owner_print_queue_digest("muteteam_ceremony")


def laos_print_queue_digest():
    _owner_print_queue_digest("laos")


def ratchaprasong_print_queue_digest():
    _owner_print_queue_digest("ratchaprasong")

# --- [NEWS] 13. DAILY EVENT SUMMARY SCHEDULER ---
# Generic per-owner daily summary, parameterized so each "mahabucha
# style" owner (mahabucha, muteteam_ceremony, laos, ratchaprasong) gets
# its own toggleable daily_summary_<owner> setting and its own
# galleries/bookings query, without copy-pasting this ~90-line body
# once per owner (previously duplicated verbatim for mahabucha and
# muteteam_ceremony).
def _owner_daily_summary(owner, setting_id, default_caption):
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return

        print(f"[TIMER] [SUMMARY] Running daily event summary check for {owner}...")
        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

        # 1. Check if daily summary is enabled for this owner
        url_settings = f"{rest_base}/system_settings"
        res_settings = requests.get(url_settings, headers=headers, params={"id": f"eq.{setting_id}", "select": "value"}, timeout=10)
        if res_settings.status_code != 200 or not res_settings.json():
            return

        setting_val = res_settings.json()[0].get("value", {})
        if not setting_val.get("enabled", False):
            print(f"[TIMER] [SUMMARY] Daily summary for {owner} is disabled.")
            return

        # 2. Get active events for this owner
        tz = timezone(timedelta(hours=7))
        now = datetime.now(tz)
        today = now.date()

        url_galleries = f"{rest_base}/galleries"
        res_galleries = requests.get(url_galleries, headers=headers, params={"owner": f"eq.{owner}", "event_date": "not.is.null", "select": "id,caption,event_date,created_at"}, timeout=10)
        if res_galleries.status_code != 200 or not res_galleries.json():
            return

        events_data = res_galleries.json()

        for ev in events_data:
            ev_date_str = ev.get("event_date")
            if not ev_date_str:
                continue
            ev_date = datetime.strptime(ev_date_str, "%Y-%m-%d").date()

            # Skip if event is already past (yesterday or earlier)
            if today > ev_date:
                continue

            # If the event_date is exactly today, it's the final day (ปิดยอด)
            is_final = (today == ev_date)

            # Fetch all bookings for this gallery (any status)
            url_bookings = f"{rest_base}/bookings"
            res_bookings = requests.get(url_bookings, headers=headers, params={"gallery_id": f"eq.{ev['id']}", "select": "total_price,tray_count,created_at"}, timeout=10)
            if res_bookings.status_code != 200:
                continue

            bookings_data = res_bookings.json()

            # 24-hour cutoff
            yesterday_2100 = now.replace(hour=21, minute=0, second=0, microsecond=0) - timedelta(days=1)
            today_2100 = now.replace(hour=21, minute=0, second=0, microsecond=0)

            total_by_price = defaultdict(int)
            today_by_price = defaultdict(int)

            for b in bookings_data:
                b_created_at_str = b.get("created_at")
                if not b_created_at_str:
                    continue

                b_created_at = datetime.fromisoformat(b_created_at_str.replace("Z", "+00:00")).astimezone(tz)
                price = b.get("total_price") or 0
                count = b.get("tray_count") or 1

                # We only count bookings created before or exactly at today 21:00
                if b_created_at <= today_2100:
                    total_by_price[price] += count

                    # If created after yesterday 21:00, it's today's increment
                    if b_created_at > yesterday_2100:
                        today_by_price[price] += count

            # Format message
            caption = ev.get("caption", default_caption)

            page_name = OWNERS.get(owner).display_name if owner in OWNERS else owner
            if is_final:
                msg = f"🔔 สรุปผลปิดยอดงานพิธี {caption}\nเพจ: {page_name}\nวันที่: {format_thai_date(today)}\n\n"
            else:
                msg = f"🔔 สรุปยอดงานพิธี {caption}\nเพจ: {page_name}\nวันที่: {format_thai_date(today)}\n\n"

            msg += "[ 📈 ยอดจองเพิ่มวันนี้ (รอบ 24 ชม.) ]\n"
            today_total = 0
            for price in sorted(today_by_price.keys()):
                c = today_by_price[price]
                today_total += c
                msg += f"- แบบ {price} จำนวน +{c} ถาด\n"
            msg += f"รวมเพิ่มวันนี้ +{today_total} ถาด\n\n"

            msg += "[ 📊 ยอดรวมสะสมทั้งหมด ]\n"
            overall_total = 0
            for price in sorted(total_by_price.keys()):
                c = total_by_price[price]
                overall_total += c
                msg += f"- แบบ {price} จำนวน {c} ถาด\n"
            msg += f"✅ รวมสะสมทั้งหมด {overall_total} ถาด\n\n"

            if is_final:
                msg += " สิ้นสุดการรับจองและปิดยอดสำหรับงานพิธีนี้เรียบร้อยครับ"

            # Send via Line
            send_line_notification(owner, msg)
            print(f"✅ [SUMMARY] Sent daily summary for {caption}")

    except Exception as e:
        print(f"❌ [SUMMARY] Error in daily event summary: {e}")


def mahabucha_daily_summary():
    _owner_daily_summary("mahabucha", "daily_summary_mahabucha", "งานพิธีมหาบูชา")


def muteteam_ceremony_daily_summary():
    _owner_daily_summary("muteteam_ceremony", "daily_summary_muteteam_ceremony", "มูเตทีม (งานพิธี)")


def laos_daily_summary():
    _owner_daily_summary("laos", "daily_summary_laos", "สยามคเณศ (ลาว)")


def ratchaprasong_daily_summary():
    _owner_daily_summary("ratchaprasong", "daily_summary_ratchaprasong", "สยามคเณศ (ราชประสงค์)")

# --- [STATS] 14. MUTETEAM MONTHLY SUMMARY SCHEDULER ---
def muteteam_monthly_summary():
    try:
        print("[TIMER] [SUMMARY] Running monthly summary check for muteteam...")
        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

        # 1. Check if monthly summary is enabled for muteteam
        url_settings = f"{rest_base}/system_settings"
        res_settings = requests.get(url_settings, headers=headers, params={"id": "eq.monthly_summary_muteteam", "select": "value"}, timeout=10)
        if res_settings.status_code != 200 or not res_settings.json():
            return
            
        setting_val = res_settings.json()[0].get("value", {})
        if not setting_val.get("enabled", False):
            print("[TIMER] [SUMMARY] Monthly summary for muteteam is disabled.")
            return

        tz = timezone(timedelta(hours=7))
        now = datetime.now(tz)
        
        # 2. Fetch all bookings for muteteam
        url_bookings = f"{rest_base}/bookings"
        res_bookings = requests.get(url_bookings, headers=headers, params={"owner": "eq.muteteam", "select": "total_price,tray_count,created_at"}, timeout=10)
        if res_bookings.status_code != 200:
            return
            
        bookings_data = res_bookings.json()
        
        # Current month cutoff
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total_by_price = defaultdict(int)
        month_by_price = defaultdict(int)
        
        for b in bookings_data:
            b_created_at_str = b.get("created_at")
            if not b_created_at_str:
                continue
                
            b_created_at = datetime.fromisoformat(b_created_at_str.replace("Z", "+00:00")).astimezone(tz)
            price = b.get("total_price") or 0
            count = b.get("tray_count") or 1
            
            total_by_price[price] += count
                
            if b_created_at >= start_of_month:
                month_by_price[price] += count
                    
        # Formatting month in Thai
        months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
        month_name = months_th[now.month]
        year_th = now.year + 543

        msg = f"🔔 สรุปยอดฝากถวายประจำเดือน {month_name} {year_th}\nเพจ: มูเตทีม\nวันที่: {format_thai_date(now)}\n\n"
        
        msg += "[ 📈 ยอดจองใหม่ในเดือนนี้ ]\n"
        month_total = 0
        for price in sorted(month_by_price.keys()):
            c = month_by_price[price]
            month_total += c
            msg += f"- แบบ {price} จำนวน {c} ถาด\n"
        msg += f"รวมยอดใหม่เดือนนี้ {month_total} ถาด\n\n"
        
        msg += "[ 📊 ยอดรวมสะสมทั้งหมด (ตั้งแต่เริ่มต้น) ]\n"
        overall_total = 0
        for price in sorted(total_by_price.keys()):
            c = total_by_price[price]
            overall_total += c
            msg += f"- แบบ {price} จำนวน {c} ถาด\n"
        msg += f"✅ รวมสะสมทั้งหมด {overall_total} ถาด\n"
        
        # Send via Line
        send_line_notification("muteteam", msg)
        print(f"✅ [SUMMARY] Sent monthly summary for muteteam")
        
    except Exception as e:
        print(f"❌ [SUMMARY] Error in muteteam monthly summary: {e}")

# Start the background scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=mahabucha_print_queue_digest, trigger="cron", hour=16, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_print_queue_digest, trigger="cron", hour=16, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_ceremony_print_queue_digest, trigger="cron", hour=16, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=laos_print_queue_digest, trigger="cron", hour=16, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=ratchaprasong_print_queue_digest, trigger="cron", hour=16, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=mahabucha_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_ceremony_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=laos_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=ratchaprasong_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=mahabucha_photo_delivery_followup, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_ceremony_photo_delivery_followup, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=laos_photo_delivery_followup, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=ratchaprasong_photo_delivery_followup, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_monthly_summary, trigger="cron", day="last", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.start()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
