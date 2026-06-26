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

app = Flask(__name__)
CORS(app)

SERVER_START_TIME = datetime.now()

# --- ⚙️ 1. CONFIG ---
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "mrtharatoy")
REPO_NAME       = os.getenv("REPO_NAME", "siamganesh-online-backend")
BRANCH          = os.getenv("BRANCH", "main")

MAHABUCHA_PAGE_ID = os.environ.get('MAHABUCHA_PAGE_ID')
MAHABUCHA_TOKEN   = os.environ.get('MAHABUCHA_TOKEN')
MUTETEAM_PAGE_ID  = os.environ.get('MUTETEAM_PAGE_ID')
MUTETEAM_TOKEN    = os.environ.get('MUTETEAM_TOKEN')
VERIFY_TOKEN      = os.environ.get('VERIFY_TOKEN')
GITHUB_TOKEN      = os.environ.get('GITHUB_TOKEN')
GEMINI_API_KEY    = os.environ.get('GEMINI_API_KEY')
SUPABASE_URL      = os.environ.get('SUPABASE_URL')
SUPABASE_KEY      = os.environ.get('SUPABASE_KEY')

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA') or os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM  = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM', "9sL5oVYE8cnPJGUL6tuDb8ZJ9MS2dk6ddZlrKLcY7SV5tYOBCLp3Cx0wCL/VJhmG7pA2f2EEmcs4UFfkCKjqfMgP7ViSBRVdbjxO/Ad//nrW6WxURrj0JdNVZuzzRdLOmiQ1MX8YNlncQJC2165FrgdB04t89/1O/w1cDnyilFU=")
LINE_GROUP_ID_MAHABUCHA   = os.environ.get('LINE_GROUP_ID_MAHABUCHA')
LINE_GROUP_ID_MUTETEAM    = os.environ.get('LINE_GROUP_ID_MUTETEAM')

CACHED_FILES = {"mahabucha": {}, "muteteam": {}}
TOTAL_IMAGES_SIZE = {"mahabucha": 0, "muteteam": 0}
FILES_LOADED = False
LAST_CACHE_REFRESH = 0
lock = threading.Lock()

# --- 📂 2. GITHUB FILES ---
def update_file_list():
    global CACHED_FILES, TOTAL_IMAGES_SIZE, FILES_LOADED
    print("🔄 Updating image list from GitHub...")
    headers = {"User-Agent": "Siamganesh-Bot", "Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    for page in ["mahabucha", "muteteam"]:
        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/images/{page}?ref={BRANCH}"
        try:
            r = requests.get(api_url, headers=headers, timeout=15)
            if r.status_code == 200:
                files = r.json()
                temp_cache = {}
                total_size = 0
                for item in files:
                    if item['type'] == 'file' and item['name'] != '.keep':
                        name_no_ext = item['name'].rsplit('.', 1)[0].strip().lower()
                        temp_cache[name_no_ext] = item['name']
                        total_size += item.get('size', 0)
                CACHED_FILES[page] = temp_cache
                TOTAL_IMAGES_SIZE[page] = total_size
                print(f"✅ {page.upper()} loaded: {len(temp_cache)} images, Size: {total_size} bytes.")
        except Exception as e:
            print(f"❌ Error {page}: {e}")
    FILES_LOADED = True

def get_image_url(page, filename):
    return f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/images/{page}/{filename}"

# --- 💬 3. FACEBOOK TOOLS ---
def get_page_token(page_id):
    if str(page_id) == str(MAHABUCHA_PAGE_ID): return MAHABUCHA_TOKEN
    if str(page_id) == str(MUTETEAM_PAGE_ID):  return MUTETEAM_TOKEN
    return None

def send_fb_action(recipient_id, page_id, data_type, payload):
    token = get_page_token(page_id)
    if not token:
        print(f"❌ [SEND] ไม่พบ token สำหรับ page_id={page_id}")
        return False, "ไม่พบ token"
    url    = "https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": token}

    if data_type == "text":
        msg = {"text": payload, "metadata": "BOT_SENT_THIS"}
    else:
        msg = {
            "attachment": {
                "type": "image",
                "payload": {"url": payload, "is_reusable": True}
            },
            "metadata": "BOT_SENT_THIS"
        }

    data = {"recipient": {"id": recipient_id}, "message": msg}
    r = requests.post(url, params=params, json=data)

    if r.status_code == 200:
        print(f"✅ [SEND] {data_type} → {recipient_id}")
        return True, ""
    else:
        print(f"⚠️ [SEND FAIL] {r.status_code} {r.text[:200]}")
        # retry ด้วย HUMAN_AGENT tag (window 7 วัน)
        data["messaging_type"] = "MESSAGE_TAG"
        data["tag"] = "HUMAN_AGENT"
        r2 = requests.post(url, params=params, json=data)
        if r2.status_code == 200:
            print(f"✅ [SEND RETRY OK] HUMAN_AGENT {data_type} → {recipient_id}")
            return True, ""
        else:
            print(f"⚠️ [SEND RETRY FAIL] HUMAN_AGENT {r2.status_code}. Retrying with POST_PURCHASE_UPDATE...")
            data["tag"] = "POST_PURCHASE_UPDATE"
            r3 = requests.post(url, params=params, json=data)
            if r3.status_code == 200:
                print(f"✅ [SEND RETRY 2 OK] POST_PURCHASE_UPDATE {data_type} → {recipient_id}")
                return True, ""
            else:
                print(f"❌ [SEND RETRY 2 FAIL] {r3.status_code} {r3.text[:200]}")
                err_msg = r3.json().get("error", {}).get("message", r3.text[:100]) if "error" in r3.text else r3.text[:100]
                return False, f"FB Error {r3.status_code}: {err_msg}"

# --- 🧠 4. MESSAGE PROCESSOR ---

def get_booking_by_code(booking_code, owner):
    if not SUPABASE_URL or not SUPABASE_KEY: return None
    try:
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/bookings" if base.endswith("/rest/v1") else f"{base}/rest/v1/bookings"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        params = {"booking_code": f"eq.{booking_code.upper()}", "owner": f"eq.{owner}", "limit": "1"}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200 and r.json():
            return r.json()[0]
    except Exception as e:
        print(f"Supabase error get_booking: {e}")
    return None

def get_system_setting(key, default_val=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return default_val
    try:
        base = SUPABASE_URL.rstrip("/")
        url_settings = f"{base}/system_settings" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        r = requests.get(f"{url_settings}?id=eq.{key}&select=value", headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                return data[0].get("value", default_val)
    except Exception as e:
        print(f"Error fetching setting {key}: {e}")
    return default_val

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

def update_booking_auto_reply_log(booking_id, logs, status_to_set, error_msg=None):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try:
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/bookings?id=eq.{booking_id}" if base.endswith("/rest/v1") else f"{base}/rest/v1/bookings?id=eq.{booking_id}"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        
        current_logs = logs or []
        timestamp_str = datetime.utcnow().isoformat() + "Z"
        
        if error_msg:
            new_log = {"action": "auto_reply_error", "error": error_msg, "by": "ระบบอัตโนมัติ", "timestamp": timestamp_str}
            payload = {"activity_logs": current_logs + [new_log]}
        else:
            new_log = {"action": status_to_set, "by": "ระบบอัตโนมัติ", "timestamp": timestamp_str}
            payload = {"status": status_to_set, "activity_logs": current_logs + [new_log]}
            
        requests.patch(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"Supabase error update log: {e}")

def get_booking_names(booking_code):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None, None
    try:
        base = SUPABASE_URL.rstrip("/")
        if base.endswith("/rest/v1"):
            url = f"{base}/bookings"
        else:
            url = f"{base}/rest/v1/bookings"
        headers = {
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        }
        params = {
            "select":       "person1_name,person2_name",
            "booking_code": f"eq.{booking_code}",
            "limit":        "1",
        }
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200 and r.json():
            row = r.json()[0]
            return row.get("person1_name"), row.get("person2_name")
    except Exception as e:
        print(f"Supabase error: {e}")
    return None, None

def force_complete_booking_by_psid(psid):
    if not SUPABASE_URL or not SUPABASE_KEY: return
    try:
        base = SUPABASE_URL.rstrip("/")
        # Find active ready_to_send booking for this PSID
        url = f"{base}/bookings?psid=eq.{psid}&status=eq.ready_to_send" if base.endswith("/rest/v1") else f"{base}/rest/v1/bookings?psid=eq.{psid}&status=eq.ready_to_send"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
        
        r = requests.get(f"{url}&select=id,activity_logs", headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            for row in r.json():
                b_id = row['id']
                logs = row.get('activity_logs') or []
                new_log = {"action": "completed", "by": "ระบบอัตโนมัติ (แอดมินพิมพ์ #จัดส่งสำเร็จ)", "timestamp": datetime.utcnow().isoformat() + "Z"}
                payload = {"status": "completed", "activity_logs": logs + [new_log]}
                update_url = f"{base}/bookings?id=eq.{b_id}" if base.endswith("/rest/v1") else f"{base}/rest/v1/bookings?id=eq.{b_id}"
                requests.patch(update_url, headers=headers, json=payload, timeout=10)
                print(f"✅ [FORCE COMPLETE] PSID={psid} Booking={b_id}")
    except Exception as e:
        print(f"❌ [FORCE COMPLETE ERROR] {e}")



def generate_thank_you_message(booking_code, person1_name=None, person2_name=None):
    def fallback():
        names = person1_name or "ผู้มีจิตศรัทธา"
        if person2_name:
            names = f"{person1_name}และ{person2_name}"
        return (
            f"📸 ขออนุญาตส่งมอบความสิริมงคลแด่คุณ{names}ครับ "
            f"ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ 'มูเตทีม' นะครับ 🙏✨"
        )

    if not GEMINI_API_KEY:
        return fallback()

    if person1_name and person2_name:
        name_ctx = f"ผู้ศรัทธาชื่อ {person1_name} และ {person2_name} (มาด้วยกัน 2 คน)"
    elif person1_name:
        name_ctx = f"ผู้ศรัทธาชื่อ {person1_name}"
    else:
        name_ctx = "ผู้มีจิตศรัทธา"

    prompt = (
        "คุณเป็นผู้ดูแลเพจ มูเตทีม ที่ให้บริการฝากถวายของแก่องค์เทพครับ\n\n"
        f"สร้างข้อความขอบคุณและส่งมอบภาพพิธีให้ {name_ctx}\n"
        "เงื่อนไข:\n"
        "- ต้องกล่าวถึงชื่อของผู้ศรัทธาทุกคน (อย่าลืม!)\n"
        "- สำนวนสุภาพ อ่อนน้อม ศักดิ์สิทธิ์ อบอุ่น\n"
        "- บอกว่ากำลังส่งภาพจากพิธีกรรม\n"
        "- แนะนำให้ติดตามเพจ มูเตทีม\n"
        "- ความยาว 2-3 ประโยค ไม่ยาวเกินไป\n"
        "- ลงท้ายด้วย 🙏✨\n"
        "- ตอบเฉพาะข้อความที่จะส่ง ไม่ต้องมีคำอธิบายเพิ่มเติม"
    )

    try:
        url = (
            "https://generativelanguage.googleapis.com/v1/models"
            f"/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature":     0.9,
                "maxOutputTokens": 300,
            },
        }
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            msg = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"Gemini msg for {booking_code}: {msg[:50]}...")
            return msg
        else:
            print(f"Gemini error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"Gemini API error: {e}")

    return fallback()


def process_mahabucha(target_id, text, page_id):
    pattern_regex = r'\b\d+\s*[a-z]{2}\s*\d+\b'
    matches       = re.findall(pattern_regex, text.lower())
    valid_codes   = [m.replace(" ", "").replace("\n", "") for m in matches]

    if not valid_codes:
        return

    global LAST_CACHE_REFRESH
    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED:
                update_file_list()
                LAST_CACHE_REFRESH = time.time()

    current_cache = CACHED_FILES["mahabucha"]
    
    missing_codes = [c for c in valid_codes if c not in current_cache]
    if missing_codes and (time.time() - LAST_CACHE_REFRESH > 10):
        with lock:
            if time.time() - LAST_CACHE_REFRESH > 10:
                print(f"Refreshing cache because codes were not found: {missing_codes}")
                update_file_list()
                LAST_CACHE_REFRESH = time.time()
                current_cache = CACHED_FILES["mahabucha"]

    # Removed empty folder check to allow auto-reply to trigger

    found_imgs    = []
    unknown_codes = []

    for code in valid_codes:
        if code in current_cache:
            found_imgs.append((code, current_cache[code]))
        else:
            unknown_codes.append(code)

    if found_imgs:
        intro = (
            "📸 ขออนุญาตส่งมอบความสิริมงคลผ่านภาพถ่าย ที่ใช้ในงานพิธีในครั้งนี้ครับ\n\n"
            "ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ \"มหาบูชา\" นะครับ 🙏✨"
        )
        send_fb_action(target_id, page_id, "text", intro)
        for code_key, filename in found_imgs:
            send_fb_action(target_id, page_id, "text", f"ภาพถาดถวาย รหัส : {code_key.upper()}")
            success, err_msg = send_fb_action(target_id, page_id, "image", get_image_url("mahabucha", filename))
            
            booking = get_booking_by_code(code_key, "mahabucha")
            if booking:
                if success:
                    update_booking_auto_reply_log(booking['id'], booking.get('activity_logs'), "completed")
                else:
                    update_booking_auto_reply_log(booking['id'], booking.get('activity_logs'), booking.get('status'), err_msg)

    if unknown_codes:
        setting = get_system_setting("auto_reply_not_found", {"mahabucha": True})
        if setting.get("mahabucha", True):
            msg = "⚠️ ขออภัยครับ \n\nไม่พบภาพถาดถวายจากรหัสของท่าน \n\nรบกวนรอแอดมินเข้ามาตรวจสอบให้ซักครู่นะครับ ⏳"
            send_fb_action(target_id, page_id, "text", msg)
        else:
            print(f"⏭️ [SKIP] Missing images for Mahabucha codes: {unknown_codes}. Passing silently due to setting.")


def check_and_send_catalog_codes(target_id, text, page_id):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    
    # 1. Fetch Setting
    try:
        base = SUPABASE_URL.rstrip("/")
        url_settings = f"{base}/system_settings" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings"
            
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        r = requests.get(f"{url_settings}?id=eq.auto_reply_catalog&select=value", headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                setting_val = data[0].get("value", {})
                if not setting_val.get("muteteam", False):
                    return # Feature is disabled
            else:
                return # Setting not found
    except Exception as e:
        print(f"Error fetching setting: {e}")
        return

    # 2. Extract potential codes
    words = re.findall(r'\b([A-Z0-9]+)\b', text.upper())
    if not words:
        return
        
    unique_words = list(set(words))
    
    # 3. Fetch matching catalogs
    try:
        in_query = ",".join(unique_words)
        url_catalogs = f"{base}/catalogs" if base.endswith("/rest/v1") else f"{base}/rest/v1/catalogs"
        cat_url = f"{url_catalogs}?deity_code=in.({in_query})&select=deity_code,image_url"
        r = requests.get(cat_url, headers=headers, timeout=5)
        if r.status_code == 200:
            catalogs = r.json()
            for cat in catalogs:
                img_url = cat.get("image_url")
                if img_url:
                    send_fb_action(target_id, page_id, "image", img_url)
    except Exception as e:
        print(f"Error fetching catalogs: {e}")


def process_muteteam(target_id, text, page_id):
    pattern_regex = r'(?<!\d)(?:(?:\d\s*){12})(?!\d)'
    matches       = re.findall(pattern_regex, text)
    valid_codes   = [m.replace(" ", "").replace("\n", "") for m in matches]

    # Check for catalog codes and send images if found
    check_and_send_catalog_codes(target_id, text, page_id)

    if not valid_codes:
        return

    global LAST_CACHE_REFRESH
    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED:
                update_file_list()
                LAST_CACHE_REFRESH = time.time()

    current_cache = CACHED_FILES["muteteam"]
    
    missing_some = False
    for booking_code in set(valid_codes):
        matched = [k for k in current_cache.keys() if k.startswith(booking_code)]
        if not matched:
            missing_some = True
            break
            
    if missing_some and (time.time() - LAST_CACHE_REFRESH > 10):
        with lock:
            if time.time() - LAST_CACHE_REFRESH > 10:
                print("Refreshing cache because some Muteteam codes were not found")
                update_file_list()
                LAST_CACHE_REFRESH = time.time()
                current_cache = CACHED_FILES["muteteam"]

    # Removed empty folder check to allow auto-reply to trigger

    for booking_code in set(valid_codes):
        matched_files = [
            (key, filename)
            for key, filename in current_cache.items()
            if key.startswith(booking_code)
        ]
        matched_files.sort(key=lambda x: x[0])

        if matched_files:
            p1, p2 = get_booking_names(booking_code)
            intro = generate_thank_you_message(booking_code, p1, p2)
            send_fb_action(target_id, page_id, "text", intro)
            for idx, (_, filename) in enumerate(matched_files, 1):
                send_fb_action(target_id, page_id, "text", f"ภาพถาดถวาย {idx}/{len(matched_files)}")
                send_fb_action(target_id, page_id, "image", get_image_url("muteteam", filename))
        else:
            setting = get_system_setting("auto_reply_not_found", {"muteteam": True})
            if setting.get("muteteam", True):
                msg = (
                    "⏳ เรียนผู้มีจิตศรัทธาที่นับถือครับ\n\n"
                    "ขณะนี้คณะทีมงานยังอยู่ระหว่างดำเนินการนำถาดถวายของท่าน\n"
                    "เข้าสู่พิธีกรรมอย่างเป็นขั้นตอนครับ\n\n"
                    "รบกวนรอทีมงานนำฝากถวายให้แล้วเสร็จ\n"
                    "แล้วท่านจะได้รับภาพเป็นที่ระลึกจากพิธีนะครับ 🙏✨"
                )
                send_fb_action(target_id, page_id, "text", msg)
            else:
                print(f"⏭️ [SKIP] Missing images for Muteteam code: {booking_code}. Passing silently due to setting.")


def process_message(target_id, text, page_id):
    print(f"🧠 [PROCESS] page_id={page_id} | MAHABUCHA={MAHABUCHA_PAGE_ID} | MUTETEAM={MUTETEAM_PAGE_ID}")
    if str(page_id) == str(MAHABUCHA_PAGE_ID):
        print("🔵 [ROUTE] → mahabucha")
        process_mahabucha(target_id, text, page_id)
    elif str(page_id) == str(MUTETEAM_PAGE_ID):
        print("🟣 [ROUTE] → muteteam")
        process_muteteam(target_id, text, page_id)
    else:
        print(f"❌ [ROUTE] page_id ไม่ตรงกับเพจใดเลย!")

# --- 🌐 5. WEBHOOK ---
@app.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "🟢 Siamganesh Online Backend is Live", 200

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if not data or data.get("object") != "page":
        return "ok", 200

    for entry in data.get("entry", []):
        page_id = str(entry.get("id", ""))
        for event in entry.get("messaging", []):
            sender_id    = event.get("sender", {}).get("id")
            recipient_id = event.get("recipient", {}).get("id")
            msg          = event.get("message", {})
            text         = msg.get("text", "")
            metadata     = msg.get("metadata", "")
            is_echo      = msg.get("is_echo", False)

            print(f"📩 [WEBHOOK] page={page_id} sender={sender_id} recipient={recipient_id} is_echo={is_echo} text='{text[:30]}'")

            # DEBUG LOG TO SUPABASE
            if is_echo and not metadata == "BOT_SENT_THIS":
                try:
                    if SUPABASE_URL and SUPABASE_KEY:
                        base = SUPABASE_URL.rstrip("/")
                        url = f"{base}/system_settings" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings"
                        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
                        debug_payload = {
                            "id": "debug_webhook",
                            "value": {"event": event, "time": datetime.utcnow().isoformat()}
                        }
                        requests.post(url, headers=headers, json=debug_payload, timeout=5)
                except Exception as e:
                    print("Debug log error", e)

            if metadata == "BOT_SENT_THIS":
                print("⏭️ [SKIP] BOT_SENT_THIS")
                continue
            if not text:
                print("⏭️ [SKIP] no text")
                continue

            # echo = admin พิมพ์จาก inbox → ส่งกลับหา recipient (customer)
            target_id = recipient_id if is_echo else sender_id

            if not target_id:
                print("⏭️ [SKIP] no target_id")
                continue

            # Normalize Thai text and check for keywords to avoid encoding issues with Sara Am
            if is_echo and ("#จัดส่ง" in text or "#จบงาน" in text or "#done" in text.lower()):
                print(f"✅ [DETECTED COMMAND] target={target_id} text contains closing tag")
                threading.Thread(
                    target=force_complete_booking_by_psid,
                    args=(target_id,),
                    daemon=True
                ).start()
                continue

            print(f"🚀 [DISPATCH] target={target_id} text='{text}'")
            threading.Thread(
                target=process_message,
                args=(target_id, text, page_id),
                daemon=True
            ).start()

    return "ok", 200

# --- 🔍 6. SEARCH API ---
@app.route('/api/search', methods=['GET'])
def search_api():
    global FILES_LOADED
    page = request.args.get('page', '').lower()
    code = request.args.get('code', '').lower().strip()

    if page not in ["mahabucha", "muteteam"] or not code:
        return jsonify({"found": False, "message": "ข้อมูลไม่ครบ"}), 400

    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED:
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

# --- 📂 6.5. LIST IMAGES API ---
@app.route('/api/images', methods=['GET'])
def list_images_api():
    global FILES_LOADED
    page = request.args.get('page', '').lower()

    if page not in ["mahabucha", "muteteam"]:
        return jsonify({"success": False, "message": "ระบุ page ไม่ถูกต้อง"}), 400

    if not FILES_LOADED:
        with lock:
            if not FILES_LOADED:
                update_file_list()

    current_cache = CACHED_FILES.get(page, {})
    
    results = []
    for key, filename in current_cache.items():
        code = key.split('_')[0] if '_' in key else key
        results.append({
            "code": code.upper(),
            "filename": filename,
            "image_url": get_image_url(page, filename)
        })
        
    return jsonify({"success": True, "results": results, "count": len(results)}), 200
@app.route('/api/debug-webhook', methods=['GET'])
def get_debug_webhook():
    if not SUPABASE_URL or not SUPABASE_KEY: return jsonify({"error": "no credentials"})
    try:
        base = SUPABASE_URL.rstrip("/")
        url = f"{base}/system_settings?id=eq.debug_webhook" if base.endswith("/rest/v1") else f"{base}/rest/v1/system_settings?id=eq.debug_webhook"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        r = requests.get(url, headers=headers)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 🔄 7. RELOAD CACHE API ---
@app.route('/api/reload', methods=['POST'])
def reload_cache():
    threading.Thread(target=update_file_list, daemon=True).start()
    return jsonify({"message": "กำลัง reload cache..."}), 200

# --- 📤 8. UPLOAD IMAGE API ---
@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "ไม่มีข้อมูล"}), 400

    booking_code = body.get("booking_code", "").strip()
    images       = body.get("images", [])
    owner        = body.get("owner", "muteteam").strip()

    if not booking_code or not images:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "Siamganesh-Bot",
    }

    uploaded = []
    errors   = []

    for img in images:
        index    = img.get("index", 1)
        ext      = img.get("ext", "webp").lstrip(".")
        data_b64 = img.get("data", "")

        if not data_b64:
            continue

        filename  = f"{booking_code}_{index}.{ext}"
        file_path = f"images/muteteam/{filename}"
        api_url   = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"

        if owner == "muteteam":
            if GITHUB_TOKEN:
                sha = None
                check = requests.get(api_url, headers=headers, timeout=10)
                if check.status_code == 200:
                    sha = check.json().get("sha")

                payload = {
                    "message": f"Upload photo: {filename}",
                    "content": data_b64,
                    "branch":  BRANCH,
                }
                if sha:
                    payload["sha"] = sha

                r = requests.put(api_url, headers=headers, json=payload, timeout=30)
                if r.status_code in (200, 201):
                    uploaded.append(filename)
                    print(f"OK Uploaded to GitHub: {filename}")
                else:
                    err = r.json().get("message", "unknown error")
                    errors.append(f"GitHub {filename}: {err}")
                    print(f"FAIL GitHub {filename}: {err}")
            else:
                print("Skipped GitHub upload (No Token)")
        else:
            # Mahabucha, just count it as "uploaded" so it succeeds
            uploaded.append(filename)



    if uploaded:
        threading.Thread(target=update_file_list, daemon=True).start()

    return jsonify({
        "success": len(uploaded) > 0,
        "uploaded": uploaded,
        "errors":   errors,
        "message":  f"อัปโหลดสำเร็จ {len(uploaded)}/{len(images)} รูป",
    }), 200 if uploaded else 500

# --- 📤 8.5. UPLOAD GITHUB RAW API ---
@app.route('/api/upload-github-raw', methods=['POST'])
def upload_github_raw():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "ไม่มีข้อมูล"}), 400

    owner  = body.get("owner", "").strip()
    images = body.get("images", [])

    if not owner or not images:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400

    if not GITHUB_TOKEN:
        return jsonify({"success": False, "message": "ไม่มี GITHUB_TOKEN"}), 500

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "Siamganesh-Bot",
    }

    uploaded = []
    errors   = []

    for img in images:
        filename = img.get("filename", "")
        data_b64 = img.get("data", "")

        if not filename or not data_b64:
            continue

        file_path = f"images/{owner}/{filename}"
        api_url   = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"

        sha = None
        check = requests.get(api_url, headers=headers, timeout=10)
        if check.status_code == 200:
            sha = check.json().get("sha")

        payload = {
            "message": f"Upload raw photo: {filename}",
            "content": data_b64,
            "branch":  BRANCH,
        }
        if sha:
            payload["sha"] = sha

        r = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            uploaded.append(filename)
            print(f"OK Uploaded RAW to GitHub: {filename}")
        else:
            err = r.json().get("message", "unknown error")
            errors.append(f"GitHub {filename}: {err}")
            print(f"FAIL GitHub RAW {filename}: {err}")

    if uploaded:
        threading.Thread(target=update_file_list, daemon=True).start()

    return jsonify({
        "success": len(uploaded) > 0,
        "uploaded": uploaded,
        "errors":   errors,
        "message":  f"อัปโหลดสำเร็จ {len(uploaded)}/{len(images)} รูป",
    }), 200 if uploaded else 500

# --- 🗑️ 9. DELETE IMAGE API ---
@app.route('/api/delete-image', methods=['POST'])
def delete_image():
    if not GITHUB_TOKEN:
        return jsonify({"success": False, "message": "ไม่มี GITHUB_TOKEN"}), 500

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "ไม่มีข้อมูล"}), 400

    page     = body.get("page", "").lower().strip()
    filename = body.get("filename", "").strip()

    if page not in ["mahabucha", "muteteam"] or not filename:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept":        "application/vnd.github.v3+json",
        "User-Agent":    "Siamganesh-Bot",
    }

    file_path = f"images/{page}/{filename}"
    api_url   = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}?ref={BRANCH}"

    check = requests.get(api_url, headers=headers, timeout=10)
    
    success = False
    msg = ""

    if check.status_code == 200:
        sha = check.json().get("sha")
        payload = {
            "message": f"Delete photo: {filename}",
            "sha":     sha,
            "branch":  BRANCH,
        }
        # URL for DELETE is the same but without ref parameter in path (pass it in body)
        delete_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"
        r = requests.delete(delete_url, headers=headers, json=payload, timeout=30)
        
        if r.status_code in (200, 201):
            threading.Thread(target=update_file_list, daemon=True).start()
            success = True
            msg = "ลบไฟล์ออกจาก GitHub สำเร็จ"
        else:
            err = r.json().get("message", "unknown error")
            msg = f"ลบไฟล์จาก GitHub ไม่สำเร็จ: {err}"
    else:
        msg = f"ไม่พบไฟล์ใน GitHub หรือข้ามไป ({check.status_code})"

    if success:
        return jsonify({"success": True, "message": msg}), 200
    else:
        return jsonify({"success": False, "message": msg}), 500

# --- 💌 10. GENERATE THANK YOU MESSAGE API ---
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


# --- 🔧 DEBUG GEMINI ---
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

# --- 📲 11. LINE NOTIFICATIONS ---
def get_line_token(owner):
    if owner == 'mahabucha' and LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA:
        return LINE_CHANNEL_ACCESS_TOKEN_MAHABUCHA
    if owner == 'muteteam' and LINE_CHANNEL_ACCESS_TOKEN_MUTETEAM:
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

    page_name = "มหาบูชา" if owner == "mahabucha" else "มูเตทีม"
    text = (
        f"🔔 [คิวปริ้นใหม่]\n"
        f"เพจ: {page_name}\n"
        f"วันที่: {date_str}\n"
        f"รหัสจอง: {booking_code}\n"
        f"ลูกค้า: {display_name}"
    )
    
    if owner != "mahabucha":
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

@app.route('/api/send-fb-message-manual', methods=['POST'])
def send_fb_message_manual():
    data = request.json
    owner = data.get('owner')
    psid = data.get('psid')
    message = data.get('message')
    images = data.get('images', [])

    if not owner or not psid:
        return jsonify({"success": False, "error": "Missing owner or psid"}), 400

    page_id = MAHABUCHA_PAGE_ID if owner == "mahabucha" else MUTETEAM_PAGE_ID
    
    # 1. Send Text
    if message:
        send_fb_action(psid, page_id, "text", message)
        
    # 2. Send Images
    success = True
    err_msg = ""
    for img_url in images:
        img_success, img_err = send_fb_action(psid, page_id, "image", img_url)
        if not img_success:
            success = False
            err_msg = img_err
            break
        
    if not success:
        return jsonify({"success": False, "error": err_msg}), 500
        
    return jsonify({"success": True}), 200

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

# --- 📰 12. TRENDING NEWS SCHEDULER ---
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
                f"🚨 [แจ้งเตือนกระแสสังคม]\n"
                f"พบข่าวที่น่าสนใจ ทำคอนเทนต์เพจ!\n\n"
                f"📌 ข่าว: {title}\n"
                f"🔗 แหล่งที่มา: {link}\n\n"
                f"💡 แนะนำให้แอดมินนำไปปรับใช้โพสต์หน้าเพจ ส่งกำลังใจได้เลยครับ"
            )
            
            # Send to both groups
            send_line_notification('muteteam', msg)
            send_line_notification('mahabucha', msg)
            
            # Mark as notified
            notified_news_links.add(link)
            print(f"✅ [NEWS] Sent notification for: {title}")

    except Exception as e:
        print(f"❌ [NEWS] Error checking trending news: {e}")

# --- 📰 13. DAILY EVENT SUMMARY SCHEDULER ---
def mahabucha_daily_summary():
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return
            
        print("🕒 [SUMMARY] Running daily event summary check...")
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
            print("🕒 [SUMMARY] Daily summary for mahabucha is disabled.")
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
                msg = f"🔔 สรุปผลปิดยอดงานพิธี {caption}\n📅 ประจำวันที่ {today.strftime('%d/%m/%Y')}\n\n"
            else:
                msg = f"🔔 สรุปยอดงานพิธี {caption}\n📅 ประจำวันที่ {today.strftime('%d/%m/%Y')}\n\n"
                
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
                msg += "🙏 สิ้นสุดการรับจองและปิดยอดสำหรับงานพิธีนี้เรียบร้อยครับ"
                
            # Send via Line
            send_line_notification("mahabucha", msg)
            print(f"✅ [SUMMARY] Sent daily summary for {caption}")
            
    except Exception as e:
        print(f"❌ [SUMMARY] Error in daily event summary: {e}")

# --- 📊 14. MUTETEAM MONTHLY SUMMARY SCHEDULER ---
def muteteam_monthly_summary():
    try:
        print("🕒 [SUMMARY] Running monthly summary check for muteteam...")
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
            print("🕒 [SUMMARY] Monthly summary for muteteam is disabled.")
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

# --- 📸 SERVER AI OCR ---
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
scheduler.add_job(func=muteteam_monthly_summary, trigger="cron", day="last", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))
scheduler.start()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
