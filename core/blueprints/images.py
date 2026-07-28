"""
Images blueprint (SG-B-103), extracted from app.py: `/api/images`,
`/api/reload`, `/api/upload-image`, `/api/upload-github-raw`,
`/api/delete-image`. Route logic is unchanged from the original
app.py handlers of the same name.

Upload/delete orchestration now lives in
core/services/image_upload_service.py (SG-B-202) so these routes are
just parse-request/call-service/map-response.
"""
import threading

from flask import Blueprint, request, jsonify

from config import GITHUB_TOKEN
from core.services.image_cache_service import CACHED_FILES, lock, is_loaded, update_file_list, get_image_url
from core.services.image_upload_service import upload_images_for_booking, upload_raw_images, delete_image_file

images_bp = Blueprint("images", __name__)


@images_bp.route('/api/images', methods=['GET'])
def list_images_api():
    page = request.args.get('page', '').lower()

    if page not in ["mahabucha", "muteteam", "muteteam_ceremony"]:
        return jsonify({"success": False, "message": "ระบุ page ไม่ถูกต้อง"}), 400

    if not is_loaded():
        with lock:
            if not is_loaded():
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


@images_bp.route('/api/reload', methods=['POST'])
def reload_cache():
    threading.Thread(target=update_file_list, daemon=True).start()
    return jsonify({"message": "กำลัง reload cache..."}), 200


@images_bp.route('/api/upload-image', methods=['POST'])
def upload_image():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "ไม่มีข้อมูล"}), 400

    booking_code = body.get("booking_code", "").strip()
    images       = body.get("images", [])
    owner        = body.get("owner", "muteteam").strip()

    if not booking_code or not images:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400

    result = upload_images_for_booking(booking_code, images, owner)
    return jsonify(result), 200 if result["success"] else 500


@images_bp.route('/api/upload-github-raw', methods=['POST'])
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

    result = upload_raw_images(owner, images)
    return jsonify(result), 200 if result["success"] else 500


@images_bp.route('/api/delete-image', methods=['POST'])
def delete_image():
    if not GITHUB_TOKEN:
        return jsonify({"success": False, "message": "ไม่มี GITHUB_TOKEN"}), 500

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "ไม่มีข้อมูล"}), 400

    page     = body.get("page", "").lower().strip()
    filename = body.get("filename", "").strip()

    if page not in ["mahabucha", "muteteam", "muteteam_ceremony"] or not filename:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400

    result = delete_image_file(page, filename)
    return jsonify(result), 200 if result["success"] else 500
