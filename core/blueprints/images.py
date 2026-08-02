"""Supabase Storage image-library endpoints."""
import threading

from flask import Blueprint, request, jsonify
from pydantic import ValidationError

from config import SUPABASE_URL, SUPABASE_KEY
from core.schemas import DeleteImageBody, ListImagesQuery, UploadGithubRawBody, UploadImageBody
from core.services.image_cache_service import CACHED_FILES, lock, is_loaded, update_file_list, get_image_url
from core.services.image_upload_service import upload_images_for_booking, upload_raw_images, delete_image_file

images_bp = Blueprint("images", __name__)


@images_bp.route('/api/images', methods=['GET'])
def list_images_api():
    try:
        query = ListImagesQuery(page=request.args.get('page', ''))
    except ValidationError:
        return jsonify({"success": False, "message": "ระบุ page ไม่ถูกต้อง"}), 400
    page = query.page

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

    try:
        validated = UploadImageBody(**body)
    except ValidationError:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400
    booking_code, images, owner = validated.booking_code, validated.images, validated.owner

    result = upload_images_for_booking(booking_code, images, owner)
    return jsonify(result), 200 if result["success"] else 500


@images_bp.route('/api/upload-storage-raw', methods=['POST'])
def upload_storage_raw():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "ไม่มีข้อมูล"}), 400

    try:
        validated = UploadGithubRawBody(**body)
    except ValidationError:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400
    owner, images = validated.owner, validated.images

    if not (SUPABASE_URL and SUPABASE_KEY):
        return jsonify({"success": False, "message": "ยังไม่ได้ตั้งค่า Supabase Storage"}), 500

    result = upload_raw_images(owner, images)
    return jsonify(result), 200 if result["success"] else 500


@images_bp.route('/api/delete-storage-image', methods=['POST'])
def delete_storage_image():
    if not (SUPABASE_URL and SUPABASE_KEY):
        return jsonify({"success": False, "message": "ยังไม่ได้ตั้งค่า Supabase Storage"}), 500

    body = request.get_json(silent=True)
    if not body:
        return jsonify({"success": False, "message": "ไม่มีข้อมูล"}), 400

    try:
        validated = DeleteImageBody(**body)
    except ValidationError:
        return jsonify({"success": False, "message": "ข้อมูลไม่ครบ"}), 400
    page, filename = validated.page, validated.filename

    result = delete_image_file(page, filename)
    return jsonify(result), 200 if result["success"] else 500
