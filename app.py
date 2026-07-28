import os
import re
import json
import threading
import requests
import time
import feedparser
import psutil
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup

from flask import Flask, request, jsonify
from flask_cors import CORS

from config import (
    GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY,
    LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA,
    LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM, LINE_GROUP_ID_MAHABUCHA,
    LINE_GROUP_ID_MUTETEAM, ALLOWED_ORIGINS,
)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

SERVER_START_TIME = datetime.now()

# --- [FILE] 2. GITHUB FILES (moved to core/services/image_cache_service.py, SG-B-103a) ---
# GITHUB_USERNAME/REPO_NAME/BRANCH/GITHUB_TOKEN and get_last_refresh/
# touch_last_refresh have no remaining direct callers in app.py now that
# the images blueprint (SG-B-103) and messenger service (SG-B-102a) own
# every call site that needed them.
from core.services.image_cache_service import (
    CACHED_FILES, TOTAL_IMAGES_SIZE, lock, is_loaded, update_file_list, get_image_url,
)

# --- [FB] 3. FACEBOOK TOOLS (moved to core/clients/facebook_client.py, SG-B-102) ---
# get_page_token/send_fb_action have no remaining direct callers in
# app.py now that the messenger blueprint owns their only call sites.

# --- [PROCESS] 4. MESSAGE PROCESSOR ---
# Supabase booking/setting queries moved to core/repositories/booking_repository.py (SG-B-102).
# get_booking_by_code/get_system_setting/update_booking_auto_reply_log have no
# remaining direct callers in app.py -- only get_booking_names is still used
# here (by /api/generate-message and /api/debug-gemini, not yet extracted).
from core.repositories.booking_repository import get_booking_names
# Gemini thank-you message generation moved to core/services/ai_service.py (SG-B-102)
from core.services.ai_service import generate_thank_you_message
# Message routing/matching moved to core/services/messenger_service.py and
# core/blueprints/messenger.py (SG-B-102) -- no remaining direct callers here.


def get_supabase_storage_stats(bucket_name, prefix=""):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return 0, 0
    try:
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/storage/v1/object/list/{bucket_name}"
        headers = {
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        payload = {"prefix": prefix, "limit": 1000, "offset": 0}
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if r.status_code != 200:
            return 0, 0
            
        data = r.json()
        count = 0
        size = 0
        
        for item in data:
            if item.get("id") is None: # It's a folder!
                folder_name = item.get("name")
                if folder_name and folder_name != ".emptyFolderPlaceholder":
                    new_prefix = f"{prefix}{folder_name}/" if prefix else f"{folder_name}/"
                    sub_count, sub_size = get_supabase_storage_stats(bucket_name, new_prefix)
                    count += sub_count
                    size += sub_size
            else: # It's a file
                count += 1
                size += item.get("metadata", {}).get("size", 0)
                
        return count, size
    except Exception as e:
        print(f"Supabase storage stats error: {e}")
    return 0, 0

# --- 🌐 5. WEBHOOK (moved to core/blueprints/messenger.py, SG-B-102) ---
from core.blueprints.messenger import messenger_bp
app.register_blueprint(messenger_bp)

# --- [SEARCH] 6. SEARCH API ---
@app.route('/api/search', methods=['GET'])
def search_api():
    page = request.args.get('page', '').lower()
    code = request.args.get('code', '').lower().strip()

    if page not in ["mahabucha", "muteteam", "muteteam_ceremony"] or not code:
        return jsonify({"found": False, "message": "ข้อมูลไม่ครบ"}), 400

    if not is_loaded():
        with lock:
            if not is_loaded():
                update_file_list()

    current_cache = CACHED_FILES.get(page, {})

    if page == "muteteam":
        matched = [
            {"code": key.upper(), "image_url": get_image_url(page, filename)}
            for key, filename in sorted(current_cache.items())
            if key.startswith(code)
        ]
        if matched:
            return jsonify({"found": True, "results": matched, "count": len(matched)}), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404
    else:
        if code in current_cache:
            return jsonify({
                "found": True,
                "code": code.upper(),
                "image_url": get_image_url(page, current_cache[code])
            }), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404

# --- [FILE] 6.5 / 7 / 8 / 8.5 / 9 IMAGES API (moved to core/blueprints/images.py, SG-B-103) ---
from core.blueprints.images import images_bp
app.register_blueprint(images_bp)

# --- [MAIL] 10. GENERATE THANK YOU MESSAGE API ---
@app.route('/api/generate-message', methods=['GET'])
def generate_message_api():
    booking_code = request.args.get('booking_code', '').strip()
    if not booking_code:
        return jsonify({"success": False, "message": "กรุณาระบุ booking_code"}), 400

    p1, p2 = get_booking_names(booking_code)
    msg = generate_thank_you_message(booking_code, p1, p2)

    return jsonify({
        "success":      True,
        "booking_code": booking_code,
        "person1_name": p1,
        "person2_name": p2,
        "message":      msg,
    }), 200


# --- [DEBUG] DEBUG GEMINI ---
@app.route('/api/debug-gemini', methods=['GET'])
def debug_gemini():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set"}), 500

    booking_code = request.args.get('booking_code', 'TEST001')
    p1, p2 = get_booking_names(booking_code)

    prompt = f"สวัสดีครับ ช่วยสร้างข้อความขอบคุณสั้นๆ สำหรับคุณ{p1 or 'ผู้มีจิตศรัทธา'} ที่มาฝากถวายของกับเพจมูเตทีม"

    try:
        url = (
            "https://generativelanguage.googleapis.com/v1/models"
            f"/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 200},
        }
        r = requests.post(url, json=payload, timeout=15)
        return jsonify({
            "status_code":    r.status_code,
            "gemini_key_set": bool(GEMINI_API_KEY),
            "key_prefix":     GEMINI_API_KEY[:8] + "..." if GEMINI_API_KEY else None,
            "person1_name":   p1,
            "person2_name":   p2,
            "raw_response":   r.json() if r.headers.get("content-type","").startswith("application/json") else r.text[:500],
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "gemini_key_set": bool(GEMINI_API_KEY)}), 500

# --- [NOTIFY] 11. LINE NOTIFICATIONS ---
def get_line_token(owner):
    if owner == 'mahabucha' and LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA:
        return LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA
    if owner in ['muteteam', 'muteteam_ceremony'] and LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM:
        return LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM
    return LINE_CHANNEL_ACCESS_TOKEN

def send_line_notification(owner, text):
    token = get_line_token(owner)
    if not token:
        print(f"❌ [LINE] Missing LINE_CHANNEL_ACCESS_TOKEN for {owner}")
        return False, f"Missing LINE_CHANNEL_ACCESS_TOKEN for {owner}"
        
    group_id = LINE_GROUP_ID_MAHABUCHA if owner == 'mahabucha' else LINE_GROUP_ID_MUTETEAM
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

@app.route('/api/line-quota', methods=['GET'])
def line_quota():
    def fetch_quota(token):
        if not token: return None
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

    return jsonify({
        "muteteam": fetch_quota(get_line_token('muteteam')),
        "mahabucha": fetch_quota(get_line_token('mahabucha'))
    }), 200




@app.route('/api/line-webhook', methods=['POST'])
def line_webhook():
    try:
        # รับข้อมูลมาเฉยๆ ไม่ต้องปริ้น log แล้ว ป้องกัน log เต็ม
        body = request.get_json()
        return "OK", 200
    except Exception as e:
        print(f"Error handling LINE webhook: {e}")
        return "Error", 500

@app.route('/api/notify-photo', methods=['POST'])
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

@app.route('/api/line-quota', methods=['GET'])
def get_line_quota():
    owner = request.args.get('owner', 'mahabucha')
    token = LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA if owner == 'mahabucha' else LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM
    if not token:
        return jsonify({"error": f"No token for {owner}"}), 500
    
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get("https://api.line.me/v2/bot/message/quota/consumption", headers=headers)
    r2 = requests.get("https://api.line.me/v2/bot/message/quota", headers=headers)
    
    return jsonify({
        "consumption": r.json(),
        "quota": r2.json()
    }), 200

@app.route('/api/system-status', methods=['GET'])
def system_status():
    uptime = datetime.now() - SERVER_START_TIME
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    # DB connection check
    db_status = "error"
    db_latency = 0
    total_bookings = 0
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            start_t = time.time()
            base = SUPABASE_URL.rstrip("/")
            url = f"{base}/rest/v1/bookings?select=id&limit=1"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
            r = requests.get(url, headers=headers, timeout=5)
            r.raise_for_status()
            db_latency = int((time.time() - start_t) * 1000)
            db_status = "ok"

            # Get total count
            url_count = f"{base}/rest/v1/bookings?select=id"
            headers_count = headers.copy()
            headers_count["Prefer"] = "count=exact"
            headers_count["Range"] = "0-0"
            r_count = requests.head(url_count, headers=headers_count, timeout=5)
            content_range = r_count.headers.get("Content-Range", "")
            if "/" in content_range:
                total_bookings = int(content_range.split("/")[1])
        except Exception:
            pass

    # External APIs check
    apis = {
        "gemini_api": bool(GEMINI_API_KEY),
        "line_notify": bool(LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA or LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM),
        "timezone": "Asia/Bangkok",
        "fb_graph": bool(os.environ.get('MUTETEAM_TOKEN') or os.environ.get('MAHABUCHA_TOKEN'))
    }

    # Background Jobs info
    jobs = {
        "trending_news": getattr(app, 'last_trending_news_time', None),
        "auto_catalog": getattr(app, 'last_auto_catalog_time', None),
    }

    total_images_github = len(CACHED_FILES.get("mahabucha", {})) + len(CACHED_FILES.get("muteteam", {}))
    total_images_size_github_mb = (TOTAL_IMAGES_SIZE.get("mahabucha", 0) + TOTAL_IMAGES_SIZE.get("muteteam", 0)) / (1024 * 1024)

    supabase_count, supabase_size = get_supabase_storage_stats("portfolio")
    supabase_size_mb = supabase_size / (1024 * 1024)

    total_images = total_images_github + supabase_count
    total_images_size_mb = total_images_size_github_mb + supabase_size_mb

    return jsonify({
        "server": {
            "cpu_percent": cpu_percent,
            "ram_percent": mem.percent,
            "ram_used_mb": mem.used // (1024*1024),
            "ram_total_mb": mem.total // (1024*1024),
            "disk_percent": disk.percent,
            "uptime_seconds": uptime.total_seconds()
        },
        "database": {
            "status": db_status,
            "latency_ms": db_latency,
            "total_bookings": total_bookings,
            "total_images": total_images,
            "total_images_size_mb": round(total_images_size_mb, 2)
        },
        "storage": {
            "github": {
                "count": total_images_github,
                "size_mb": round(total_images_size_github_mb, 2),
                "limit_mb": 1024
            },
            "supabase": {
                "count": supabase_count,
                "size_mb": round(supabase_size_mb, 2),
                "limit_mb": 1024
            }
        },
        "apis": apis,
        "jobs": jobs
    }), 200


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

# --- [PHOTO] SERVER AI OCR ---
@app.route('/api/ocr-image', methods=['POST'])
def ocr_image():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY is not configured"}), 500
        
    try:
        data = request.get_json(silent=True)
        if not data or not data.get("image"):
            return jsonify({"error": "No image data provided"}), 400
            
        base64_image = data["image"]
        mime_type = "image/jpeg"
        # Remove prefix if present (e.g. data:image/png;base64,)
        if "," in base64_image:
            prefix = base64_image.split(",")[0]
            if "data:" in prefix and ";base64" in prefix:
                mime_type = prefix.split("data:")[1].split(";base64")[0]
            base64_image = base64_image.split(",")[1]
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": "Find and extract the booking/tracking code from this image. The code ALWAYS matches one of these two formats: 1) Exactly 12 digits (e.g. 123456789012). 2) Numbers followed by 2 uppercase letters followed by numbers (e.g. 12MB010001). Return ONLY the code itself, with no spaces, no punctuation, and no other text. If you absolutely cannot find any code matching these formats, return NOT_FOUND."
                        },
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1
            }
        }
        
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            result_data = r.json()
            if "candidates" in result_data and len(result_data["candidates"]) > 0:
                text = result_data["candidates"][0]["content"]["parts"][0].get("text", "").strip()
                return jsonify({"code": text})
            else:
                return jsonify({"code": "NOT_FOUND"})
        else:
            return jsonify({"error": f"Gemini API returned {r.status_code}", "details": r.text}), 500
            
    except Exception as e:
        print(f"Error in OCR image API: {e}")
        return jsonify({"error": str(e)}), 500

# Start the background scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_trending_news, trigger="interval", hours=1, next_run_time=datetime.now())
scheduler.add_job(func=mahabucha_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_ceremony_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.add_job(func=muteteam_monthly_summary, trigger="cron", day="last", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.start()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
