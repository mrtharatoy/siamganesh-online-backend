"""
Facebook Messenger Send API client, extracted from app.py (SG-B-102).

Logic unchanged from the original app.py functions of the same name --
only the import source for page-token config moved.
"""
import requests

from config import MAHABUCHA_PAGE_ID, MAHABUCHA_TOKEN, MUTETEAM_PAGE_ID, MUTETEAM_TOKEN


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
