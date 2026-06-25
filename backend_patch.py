import sys

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    code_to_insert = """# --- 📊 14. MUTETEAM MONTHLY SUMMARY SCHEDULER ---
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

        msg = f"🔔 สรุปยอดฝากถวายประจำเดือน {month_name} {year_th}\\nเพจ: มูเตทีม\\n\\n"
        
        msg += "[ 📈 ยอดจองใหม่ในเดือนนี้ ]\\n"
        month_total = 0
        for price in sorted(month_by_price.keys()):
            c = month_by_price[price]
            month_total += c
            msg += f"- แบบ {price} จำนวน {c} ถาด\\n"
        msg += f"รวมยอดใหม่เดือนนี้ {month_total} ถาด\\n\\n"
        
        msg += "[ 📊 ยอดรวมสะสมทั้งหมด (ตั้งแต่เริ่มต้น) ]\\n"
        overall_total = 0
        for price in sorted(total_by_price.keys()):
            c = total_by_price[price]
            overall_total += c
            msg += f"- แบบ {price} จำนวน {c} ถาด\\n"
        msg += f"✅ รวมสะสมทั้งหมด {overall_total} ถาด\\n"
        
        # Send via Line
        send_line_notification("muteteam", msg)
        print(f"✅ [SUMMARY] Sent monthly summary for muteteam")
        
    except Exception as e:
        print(f"❌ [SUMMARY] Error in muteteam monthly summary: {e}")

"""
    
    # Insert code right before OCR
    ocr_section = "# --- 📸 SERVER AI OCR ---"
    if ocr_section in content and code_to_insert not in content:
        content = content.replace(ocr_section, code_to_insert + ocr_section)
        
    # Patch scheduler
    scheduler_code = """scheduler.add_job(func=mahabucha_daily_summary, trigger="cron", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))"""
    new_scheduler_code = scheduler_code + """\nscheduler.add_job(func=muteteam_monthly_summary, trigger="cron", day="last", hour=21, minute=0, timezone=timezone(timedelta(hours=7)))"""
    
    if scheduler_code in content and new_scheduler_code not in content:
        content = content.replace(scheduler_code, new_scheduler_code)
        
    with open(filepath, 'w') as f:
        f.write(content)
        
if __name__ == "__main__":
    patch_file('app.py')
    print("Patched app.py")
