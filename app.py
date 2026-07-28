import os
import re
import json
import threading
import requests
import time
import feedparser
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import (
    GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY, ALLOWED_ORIGINS,
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# Read by system_status via flask.current_app (core/blueprints/system.py,
# SG-B-106) rather than a direct import, to avoid a circular import.
app.server_start_time = datetime.now()

# --- Centralized error handlers (SG-B-107) ---
from core.errors import register_error_handlers
register_error_handlers(app)

# --- [FILE] 2. GITHUB FILES (moved to core/services/image_cache_service.py, SG-B-103a) ---
# CACHED_FILES/TOTAL_IMAGES_SIZE/lock/is_loaded/get_image_url have no
# remaining direct callers in app.py now that the images (SG-B-103) and
# system (SG-B-106) blueprints own every call site that needed them.
# update_file_list() is still called once below to warm the cache at
# process startup, exactly as before.
from core.services.image_cache_service import update_file_list

# --- [FB] 3. FACEBOOK TOOLS (moved to core/clients/facebook_client.py, SG-B-102) ---
# get_page_token/send_fb_action have no remaining direct callers in
# app.py now that the messenger blueprint owns their only call sites.

# --- [PROCESS] 4. MESSAGE PROCESSOR ---
# Supabase booking/setting queries moved to core/repositories/booking_repository.py
# (SG-B-102); Gemini thank-you message generation to core/services/ai_service.py
# (SG-B-102); message routing/matching to core/services/messenger_service.py and
# core/blueprints/messenger.py (SG-B-102). get_booking_names/generate_thank_you_message
# have no remaining direct callers in app.py now that the AI blueprint (SG-B-105)
# owns their only call sites (/api/generate-message, /api/debug-gemini).


# --- 🌐 5. WEBHOOK (moved to core/blueprints/messenger.py, SG-B-102) ---
from core.blueprints.messenger import messenger_bp
app.register_blueprint(messenger_bp)


# --- [FILE] 6.5 / 7 / 8 / 8.5 / 9 IMAGES API (moved to core/blueprints/images.py, SG-B-103) ---
from core.blueprints.images import images_bp
app.register_blueprint(images_bp)

# --- [MAIL] 10 / [DEBUG] DEBUG GEMINI / [PHOTO] SERVER AI OCR (moved to core/blueprints/ai.py, SG-B-105) ---
from core.blueprints.ai import ai_bp
app.register_blueprint(ai_bp)

# --- [NOTIFY] 11. LINE NOTIFICATIONS (moved to core/blueprints/notifications.py, SG-B-104) ---
# get_line_token has no remaining direct caller in app.py; send_line_notification
# is still used by the scheduler functions below (check_trending_news,
# mahabucha_daily_summary, muteteam_ceremony_daily_summary, muteteam_monthly_summary).
from core.clients.line_client import send_line_notification
from core.blueprints.notifications import notifications_bp
app.register_blueprint(notifications_bp)

# --- [SEARCH] 6 / [SYSTEM] SYSTEM STATUS (moved to core/blueprints/system.py, SG-B-106) ---
from core.blueprints.system import system_bp
app.register_blueprint(system_bp)

update_file_list()

# --- [NEWS] 12. TRENDING NEWS SCHEDULER ---
notified_news_links = set()

def check_trending_news():
    global notified_news_links
    
    # Record job time
    app.last_trending_news_time = datetime.now().isoformat()
    
    if not GEMINI_API_KEY:
        print("❌ [NEWS] GEMINI_API_KEY missing")
        return

    # Check database settings to see if it's disabled
    if SUPABASE_URL and SUPABASE_KEY:
        base = SUPABASE_URL.rstrip("/")
        url_settings = f"{base}/system_settings" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        try:
            r_set = requests.get(f"{url_settings}?id=eq.trending_news_notify&select=value", headers=headers, timeout=5)
            if r_set.status_code == 200:
                data_set = r_set.json()
                if len(data_set) > 0:
                    val = data_set[0].get("value", {})
                    if val.get("enabled") is False:
                        print("ℹ️ [NEWS] Trending news notification is disabled in settings.")
                        return
        except Exception as e:
            print(f"⚠️ [NEWS] Failed to fetch settings: {e}")

    try:
        feed = feedparser.parse("https://news.google.com/rss/headlines/section/geo/TH?hl=th&gl=TH&ceid=TH:th")
        entries = feed.entries[:15]
        
        # Filter out already notified
        new_entries = [e for e in entries if getattr(e, 'link', '') not in notified_news_links]
        if not new_entries:
            return

        headlines_text = "\n".join([f"- {e.title} (URL: {e.link})" for e in new_entries])
        
        prompt = f"""
วิเคราะห์หัวข้อข่าวต่อไปนี้ ว่ามีข่าวที่เป็นกระแสสังคม ข่าวใหญ่ระดับประเทศ ข่าวเกี่ยวกับความเชื่อ/สายมู หรือข่าวที่ส่งผลกระทบต่อจิตใจคน (เช่น ภัยพิบัติ อุบัติเหตุ เรื่องเศร้า หรือเรื่องที่คนกำลังให้ความสนใจ) ที่เหมาะสมกับการนำไปโพสต์ในเพจสายมูเตลูเพื่อเกาะกระแส ส่งกำลังใจ หรือชวนคนมาสวดมนต์ขอพรหรือไม่

หัวข้อข่าว:
{headlines_text}

ตอบกลับเป็น JSON Format เท่านั้น โดยมีโครงสร้างดังนี้:
{{
  "found": true หรือ false,
  "title": "หัวข้อข่าวที่เลือก",
  "link": "ลิงก์ข่าวที่เลือก (ดึงมาจาก URL ใน input)",
  "reason": "ทำไมถึงเลือกข่าวนี้"
}}
ถ้าไม่มีข่าวที่เหมาะสมเลย ให้ตอบ {{"found": false}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"}
        }
        r = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
        r.raise_for_status()
        
        data = r.json()
        try:
            content_text = data['candidates'][0]['content']['parts'][0]['text']
            result = json.loads(content_text)
        except Exception as e:
            print(f"❌ [NEWS] Failed to parse Gemini response: {e}")
            return

        if result.get("found"):
            title = result.get("title")
            link = result.get("link")
            
            msg = (
                f"[ALERT] [แจ้งเตือนกระแสสังคม]\n"
                f"พบข่าวที่น่าสนใจ ทำคอนเทนต์เพจ!\n\n"
                f"[PIN] ข่าว: {title}\n"
                f"[LINK] แหล่งที่มา: {link}\n\n"
                f"[HINT] แนะนำให้แอดมินนำไปปรับใช้โพสต์หน้าเพจ ส่งกำลังใจได้เลยครับ"
            )
            
            # Send to both groups
            send_line_notification('muteteam', msg)
            send_line_notification('mahabucha', msg)
            
            # Mark as notified
            notified_news_links.add(link)
            print(f"✅ [NEWS] Sent notification for: {title}")

    except Exception as e:
        print(f"❌ [NEWS] Error checking trending news: {e}")

# --- [NEWS] 13. DAILY EVENT SUMMARY SCHEDULER ---
def mahabucha_daily_summary():
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return
            
        print("[TIMER] [SUMMARY] Running daily event summary check...")
        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

        # 1. Check if daily summary is enabled for mahabucha
        url_settings = f"{rest_base}/system_settings"
        res_settings = requests.get(url_settings, headers=headers, params={"id": "eq.daily_summary_mahabucha", "select": "value"}, timeout=10)
        if res_settings.status_code != 200 or not res_settings.json():
            return
            
        setting_val = res_settings.json()[0].get("value", {})
        if not setting_val.get("enabled", False):
            print("[TIMER] [SUMMARY] Daily summary for mahabucha is disabled.")
            return
            
        # 2. Get active events for mahabucha
        tz = timezone(timedelta(hours=7))
        now = datetime.now(tz)
        today = now.date()
        
        url_galleries = f"{rest_base}/galleries"
        res_galleries = requests.get(url_galleries, headers=headers, params={"owner": "eq.mahabucha", "event_date": "not.is.null", "select": "id,caption,event_date,created_at"}, timeout=10)
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
            caption = ev.get("caption", "งานพิธีมหาบูชา")
            
            if is_final:
                msg = f"🔔 สรุปผลปิดยอดงานพิธี {caption}\n[DATE] ประจำวันที่ {today.strftime('%d/%m/%Y')}\n\n"
            else:
                msg = f"🔔 สรุปยอดงานพิธี {caption}\n[DATE] ประจำวันที่ {today.strftime('%d/%m/%Y')}\n\n"
                
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
            send_line_notification("mahabucha", msg)
            print(f"✅ [SUMMARY] Sent daily summary for {caption}")
            
    except Exception as e:
        print(f"❌ [SUMMARY] Error in daily event summary: {e}")



def muteteam_ceremony_daily_summary():
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return
            
        print("[TIMER] [SUMMARY] Running daily event summary check...")
        base = SUPABASE_URL.rstrip("/")
        rest_base = base if base.endswith("/rest/v1") else f"{base}/rest/v1"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

        # 1. Check if daily summary is enabled for muteteam_ceremony
        url_settings = f"{rest_base}/system_settings"
        res_settings = requests.get(url_settings, headers=headers, params={"id": "eq.daily_summary_muteteam_ceremony", "select": "value"}, timeout=10)
        if res_settings.status_code != 200 or not res_settings.json():
            return
            
        setting_val = res_settings.json()[0].get("value", {})
        if not setting_val.get("enabled", False):
            print("[TIMER] [SUMMARY] Daily summary for muteteam_ceremony is disabled.")
            return
            
        # 2. Get active events for muteteam_ceremony
        tz = timezone(timedelta(hours=7))
        now = datetime.now(tz)
        today = now.date()
        
        url_galleries = f"{rest_base}/galleries"
        res_galleries = requests.get(url_galleries, headers=headers, params={"owner": "eq.muteteam_ceremony", "event_date": "not.is.null", "select": "id,caption,event_date,created_at"}, timeout=10)
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
            caption = ev.get("caption", "มูเตทีม (งานพิธี)")
            
            if is_final:
                msg = f"🔔 สรุปผลปิดยอดงานพิธี {caption}\n[DATE] ประจำวันที่ {today.strftime('%d/%m/%Y')}\n\n"
            else:
                msg = f"🔔 สรุปยอดงานพิธี {caption}\n[DATE] ประจำวันที่ {today.strftime('%d/%m/%Y')}\n\n"
                
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
            send_line_notification("muteteam_ceremony", msg)
            print(f"✅ [SUMMARY] Sent daily summary for {caption}")
            
    except Exception as e:
        print(f"❌ [SUMMARY] Error in daily event summary: {e}")

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

        msg = f"🔔 สรุปยอดฝากถวายประจำเดือน {month_name} {year_th}\nเพจ: มูเตทีม\n\n"
        
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
scheduler.add_job(func=check_trending_news, trigger="interval", hours=1, next_run_time=datetime.now())
scheduler.add_job(func=mahabucha_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_ceremony_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_monthly_summary, trigger="cron", day="last", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.start()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
