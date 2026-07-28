"""
AI blueprint (SG-B-105), extracted from app.py: `/api/generate-message`,
`/api/debug-gemini`, `/api/ocr-image`. Route logic is unchanged from
the original app.py handlers of the same name -- only the import
source moved (get_booking_names/generate_thank_you_message already
extracted to core/repositories/booking_repository.py and
core/services/ai_service.py since SG-B-102a).
"""
from flask import Blueprint, request, jsonify

from config import GEMINI_API_KEY
from core.clients.gemini_client import generate_content
from core.repositories.booking_repository import get_booking_names
from core.services.ai_service import generate_thank_you_message

ai_bp = Blueprint("ai", __name__)


@ai_bp.route('/api/generate-message', methods=['GET'])
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


@ai_bp.route('/api/debug-gemini', methods=['GET'])
def debug_gemini():
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set"}), 500

    booking_code = request.args.get('booking_code', 'TEST001')
    p1, p2 = get_booking_names(booking_code)

    prompt = f"สวัสดีครับ ช่วยสร้างข้อความขอบคุณสั้นๆ สำหรับคุณ{p1 or 'ผู้มีจิตศรัทธา'} ที่มาฝากถวายของกับเพจมูเตทีม"

    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.9, "maxOutputTokens": 200},
        }
        r = generate_content("gemini-1.5-flash", payload, api_version="v1", timeout=15)
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


@ai_bp.route('/api/ocr-image', methods=['POST'])
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

        r = generate_content("gemini-2.5-flash-lite", payload, api_version="v1beta", timeout=20)
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
