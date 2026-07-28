"""
Images blueprint (SG-B-103), extracted from app.py: `/api/images`,
`/api/reload`, `/api/upload-image`, `/api/upload-github-raw`,
`/api/delete-image`. Route logic is unchanged from the original
app.py handlers of the same name.

GitHub Contents API calls now go through core/clients/github_client.py
(SG-B-201) instead of building requests inline -- get_file_sha() (no
ref) for the upload routes and get_file_sha_at_ref() (with ref) for
delete_image, matching each route's original existence-check exactly.
"""
import threading

from flask import Blueprint, request, jsonify

from config import BRANCH, GITHUB_TOKEN
from core.clients.github_client import get_file_sha, get_file_sha_at_ref, put_file, delete_file
from core.services.image_cache_service import CACHED_FILES, lock, is_loaded, update_file_list, get_image_url

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

        if owner == "muteteam":
            if GITHUB_TOKEN:
                sha = get_file_sha(file_path)
                success, err = put_file(file_path, data_b64, f"Upload photo: {filename}", branch=BRANCH, sha=sha)
                if success:
                    uploaded.append(filename)
                    print(f"OK Uploaded to GitHub: {filename}")
                else:
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

    uploaded = []
    errors   = []

    for img in images:
        filename = img.get("filename", "")
        data_b64 = img.get("data", "")

        if not filename or not data_b64:
            continue

        file_path = f"images/{owner}/{filename}"

        sha = get_file_sha(file_path)
        success, err = put_file(file_path, data_b64, f"Upload raw photo: {filename}", branch=BRANCH, sha=sha)
        if success:
            uploaded.append(filename)
            print(f"OK Uploaded RAW to GitHub: {filename}")
        else:
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

    file_path = f"images/{page}/{filename}"
    sha, check_status = get_file_sha_at_ref(file_path, BRANCH)

    success = False
    msg = ""

    if sha is not None:
        deleted, err = delete_file(file_path, sha, f"Delete photo: {filename}", branch=BRANCH)
        if deleted:
            threading.Thread(target=update_file_list, daemon=True).start()
            success = True
            msg = "ลบไฟล์ออกจาก GitHub สำเร็จ"
        else:
            msg = f"ลบไฟล์จาก GitHub ไม่สำเร็จ: {err}"
    else:
        msg = f"ไม่พบไฟล์ใน GitHub หรือข้ามไป ({check_status})"

    if success:
        return jsonify({"success": True, "message": msg}), 200
    else:
        return jsonify({"success": False, "message": msg}), 500
