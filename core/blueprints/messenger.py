"""
Messenger blueprint (SG-B-102), extracted from app.py: `/` (Facebook
webhook verify + receive), `/api/debug-webhook`, and
`/api/send-fb-message-manual`. Route logic is unchanged from the
original app.py handlers of the same name -- only the import sources
moved (business logic already lived in core/services/messenger_service.py
and core/clients/facebook_client.py since SG-B-102a).
"""
import threading
from datetime import datetime

from flask import Blueprint, request, jsonify

from config import VERIFY_TOKEN, SUPABASE_URL, SUPABASE_KEY, MAHABUCHA_PAGE_ID, MUTETEAM_PAGE_ID
from core.clients.facebook_client import send_fb_action
from core.clients.supabase_rest_client import get_debug_webhook as fetch_debug_webhook, upsert_debug_webhook
from core.services.messenger_service import process_message

messenger_bp = Blueprint("messenger", __name__)


@messenger_bp.route('/', methods=['GET'])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "[OK] Siamganesh Online Backend is Live", 200


@messenger_bp.route('/', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if not data or data.get("object") != "page":
        return "ok", 200

    for entry in data.get("entry", []):
        page_id = str(entry.get("id", ""))

        # Merge messaging and standby events for Handover Protocol
        msg_events = entry.get("messaging") or []
        standby_events = entry.get("standby") or []
        events = msg_events + standby_events

        for event in events:
            sender_id    = event.get("sender", {}).get("id")
            recipient_id = event.get("recipient", {}).get("id")
            msg          = event.get("message", {})
            text         = msg.get("text", "")
            metadata     = msg.get("metadata", "")
            is_echo      = msg.get("is_echo", False)

            print(f"[MSG] [WEBHOOK] page={page_id} sender={sender_id} recipient={recipient_id} is_echo={is_echo} text='{text[:30]}'")

            # DEBUG LOG TO SUPABASE
            if is_echo and not metadata == "BOT_SENT_THIS":
                try:
                    if SUPABASE_URL and SUPABASE_KEY:
                        upsert_debug_webhook(SUPABASE_URL, SUPABASE_KEY, event, datetime.utcnow().isoformat())
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


            print(f"[DISPATCH] [DISPATCH] target={target_id} text='{text}'")
            threading.Thread(
                target=process_message,
                args=(target_id, text, page_id),
                daemon=True
            ).start()

    return "ok", 200


@messenger_bp.route('/api/debug-webhook', methods=['GET'])
def get_debug_webhook():
    if not SUPABASE_URL or not SUPABASE_KEY: return jsonify({"error": "no credentials"})
    try:
        r = fetch_debug_webhook(SUPABASE_URL, SUPABASE_KEY)
        return jsonify(r.json()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@messenger_bp.route('/api/send-fb-message-manual', methods=['POST'])
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
