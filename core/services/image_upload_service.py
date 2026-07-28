"""
Upload/delete orchestration for GitHub-backed images (SG-B-202),
extracted from core/blueprints/images.py so those routes become thin
parse-request/call-service/map-response handlers. Logic unchanged,
including the documented owner-conditional quirk in
upload_images_for_booking (API_BASELINE.md #7): owner != "muteteam"
never touches GitHub at all but is still reported as uploaded.

Each function returns a plain dict already shaped like the route's
JSON response body; the blueprint only adds the HTTP status code.
"""
from config import BRANCH, GITHUB_TOKEN
from core.clients.github_client import get_file_sha, get_file_sha_at_ref, put_file, delete_file
from core.services.image_cache_service import update_file_list
import threading


def _refresh_cache_in_background():
    threading.Thread(target=update_file_list, daemon=True).start()


def upload_images_for_booking(booking_code, images, owner):
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
        _refresh_cache_in_background()

    return {
        "success": len(uploaded) > 0,
        "uploaded": uploaded,
        "errors":   errors,
        "message":  f"อัปโหลดสำเร็จ {len(uploaded)}/{len(images)} รูป",
    }


def upload_raw_images(owner, images):
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
        _refresh_cache_in_background()

    return {
        "success": len(uploaded) > 0,
        "uploaded": uploaded,
        "errors":   errors,
        "message":  f"อัปโหลดสำเร็จ {len(uploaded)}/{len(images)} รูป",
    }


def delete_image_file(page, filename):
    file_path = f"images/{page}/{filename}"
    sha, check_status = get_file_sha_at_ref(file_path, BRANCH)

    if sha is None:
        return {"success": False, "message": f"ไม่พบไฟล์ใน GitHub หรือข้ามไป ({check_status})"}

    deleted, err = delete_file(file_path, sha, f"Delete photo: {filename}", branch=BRANCH)
    if deleted:
        _refresh_cache_in_background()
        return {"success": True, "message": "ลบไฟล์ออกจาก GitHub สำเร็จ"}
    return {"success": False, "message": f"ลบไฟล์จาก GitHub ไม่สำเร็จ: {err}"}
