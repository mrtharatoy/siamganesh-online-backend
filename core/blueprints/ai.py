"""
AI blueprint (SG-B-105), extracted from app.py: `/api/generate-message`.
Route logic is unchanged from the original app.py handler of the same
name -- only the import source moved (get_booking_names/
generate_thank_you_message already extracted to
core/repositories/booking_repository.py and core/services/ai_service.py
since SG-B-102a). The Gemini-backed `/api/debug-gemini` and
`/api/ocr-image` routes that used to live here were removed along with
the Gemini API integration; generate_thank_you_message now always
returns its static template message.
"""
from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from core.repositories.booking_repository import get_booking_names
from core.schemas import GenerateMessageQuery
from core.services.ai_service import generate_thank_you_message

ai_bp = Blueprint("ai", __name__)


@ai_bp.route('/api/generate-message', methods=['GET'])
def generate_message_api():
    try:
        query = GenerateMessageQuery(booking_code=request.args.get('booking_code', ''))
    except ValidationError:
        return jsonify({"success": False, "message": "กรุณาระบุ booking_code"}), 400
    booking_code = query.booking_code

    p1, p2 = get_booking_names(booking_code)
    msg = generate_thank_you_message(booking_code, p1, p2)

    return jsonify({
        "success":      True,
        "booking_code": booking_code,
        "person1_name": p1,
        "person2_name": p2,
        "message":      msg,
    }), 200
