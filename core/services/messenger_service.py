"""
Facebook Messenger message routing/matching logic, extracted from
app.py (SG-B-102). Logic unchanged from the original app.py functions
of the same name -- only the import sources moved (shared image cache
from core.services.image_cache_service, FB send from
core.clients.facebook_client, Supabase queries from
core.repositories.booking_repository, Gemini message generation from
core.services.ai_service).

check_and_send_catalog_codes() still relies on `base` staying bound
across its two separate try/except blocks (assigned in the first,
read in the third) -- this is existing, slightly fragile control flow
carried over unchanged from app.py, not something this extraction
should silently "fix".
"""
import re
import time

import requests

from config import MAHABUCHA_PAGE_ID, MUTETEAM_PAGE_ID, SUPABASE_URL, SUPABASE_KEY
from core.clients.facebook_client import send_fb_action
from core.repositories.booking_repository import (
    get_booking_by_code, get_system_setting, update_booking_auto_reply_log, get_booking_names,
)
from core.services.ai_service import generate_thank_you_message
from core.services.image_cache_service import (
    CACHED_FILES, lock, is_loaded, get_last_refresh, touch_last_refresh,
    update_file_list, get_image_url,
)


def process_ceremony_flow(target_id, text, page_id, owner_key):
    pattern_regex = r'(?<!\d)\d+\s*[a-z]{2}\s*\d+(?!\d)'
    matches       = re.findall(pattern_regex, text.lower())
    valid_codes   = [m.replace(" ", "").replace("\n", "") for m in matches]

    if not valid_codes:
        return False

    if not is_loaded():
        with lock:
            if not is_loaded():
                update_file_list()
                touch_last_refresh()

    current_cache = CACHED_FILES[owner_key]

    missing_some = False
    for code in set(valid_codes):
        matched = [k for k in current_cache.keys() if k.startswith(code)]
        if not matched:
            missing_some = True
            break

    if missing_some and (time.time() - get_last_refresh() > 10):
        with lock:
            if time.time() - get_last_refresh() > 10:
                print(f"Refreshing cache because ceremony codes were not found")
                update_file_list()
                touch_last_refresh()
                current_cache = CACHED_FILES[owner_key]

    found_imgs    = []
    unknown_codes = []

    for code in set(valid_codes):
        matched_files = [
            (key, filename)
            for key, filename in current_cache.items()
            if key.startswith(code)
        ]
        matched_files.sort(key=lambda x: x[0])

        if matched_files:
            for key, filename in matched_files:
                found_imgs.append((code, filename))
        else:
            unknown_codes.append(code)

    if found_imgs:
        page_name = "มหาบูชา" if owner_key == "mahabucha" else "มูเตทีม"
        intro = (
            "[PHOTO] 📸 ขออนุญาตส่งมอบความสิริมงคลผ่านภาพถ่าย ที่ใช้ในงานพิธีในครั้งนี้ครับ\n\n"
            f"ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ \"{page_name}\" นะครับ 🙏✨\n\n"
            "//แอดมิน\n"
            "ทอย ธราธร สยามคเณศ"
        )
        send_fb_action(target_id, page_id, "text", intro)
        for code_key, filename in found_imgs:
            send_fb_action(target_id, page_id, "text", f"ภาพถาดถวาย รหัส : {code_key.upper()}")
            success, err_msg = send_fb_action(target_id, page_id, "image", get_image_url(owner_key, filename))

            booking = get_booking_by_code(code_key, owner_key)
            if booking:
                if success:
                    update_booking_auto_reply_log(booking['id'], booking.get('activity_logs'), "completed")
                else:
                    update_booking_auto_reply_log(booking['id'], booking.get('activity_logs'), booking.get('status'), err_msg)

    if unknown_codes:
        setting = get_system_setting("auto_reply_not_found", {owner_key: True})
        if setting.get(owner_key, True):
            msg = "⚠️ ขออภัยครับ \n\nไม่พบภาพถาดถวายจากรหัสของท่าน \n\nรบกวนรอแอดมินเข้ามาตรวจสอบให้ซักครู่นะครับ ⏳"
            send_fb_action(target_id, page_id, "text", msg)
        else:
            print(f"⏭️ [SKIP] Missing images for {owner_key} codes: {unknown_codes}. Passing silently due to setting.")

    return True


def process_mahabucha(target_id, text, page_id):
    process_ceremony_flow(target_id, text, page_id, "mahabucha")


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
    if process_ceremony_flow(target_id, text, page_id, "muteteam_ceremony"):
        return

    pattern_regex = r'(?<!\d)(?:(?:\d\s*){12})(?!\d)'
    matches       = re.findall(pattern_regex, text)
    valid_codes   = [m.replace(" ", "").replace("\n", "") for m in matches]

    # Check for catalog codes and send images if found
    check_and_send_catalog_codes(target_id, text, page_id)

    if not valid_codes:
        return

    if not is_loaded():
        with lock:
            if not is_loaded():
                update_file_list()
                touch_last_refresh()

    current_cache = CACHED_FILES["muteteam"]

    missing_some = False
    for booking_code in set(valid_codes):
        matched = [k for k in current_cache.keys() if k.startswith(booking_code)]
        if not matched:
            missing_some = True
            break

    if missing_some and (time.time() - get_last_refresh() > 10):
        with lock:
            if time.time() - get_last_refresh() > 10:
                print("Refreshing cache because some Muteteam codes were not found")
                update_file_list()
                touch_last_refresh()
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
                    "แล้วท่านจะได้รับภาพเป็นที่ระลึกจากพิธีนะครับ "
                )
                send_fb_action(target_id, page_id, "text", msg)
            else:
                print(f"⏭️ [SKIP] Missing images for Muteteam code: {booking_code}. Passing silently due to setting.")


def process_message(target_id, text, page_id):
    print(f"[PROCESS] [PROCESS] page_id={page_id} | MAHABUCHA={MAHABUCHA_PAGE_ID} | MUTETEAM={MUTETEAM_PAGE_ID}")
    if str(page_id) == str(MAHABUCHA_PAGE_ID):
        print("[INFO] [ROUTE] → mahabucha")
        process_mahabucha(target_id, text, page_id)
    elif str(page_id) == str(MUTETEAM_PAGE_ID):
        print("[INFO] [ROUTE] → muteteam")
        process_muteteam(target_id, text, page_id)
    else:
        print(f"❌ [ROUTE] page_id ไม่ตรงกับเพจใดเลย!")
