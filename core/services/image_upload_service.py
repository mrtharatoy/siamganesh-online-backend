"""Upload/delete operations for the Supabase-backed image library."""
import base64
import mimetypes
import threading
from urllib.parse import quote

import requests

from config import SUPABASE_URL, SUPABASE_KEY
from core.services.image_cache_service import BUCKET, LIBRARY_PREFIX, update_file_list


def _headers(extra=None):
    headers = {"apikey": SUPABASE_KEY or "", "Authorization": f"Bearer {SUPABASE_KEY or ''}"}
    if extra: headers.update(extra)
    return headers


def _path(owner, filename): return f"{LIBRARY_PREFIX}/{owner}/{filename}"


def upload_raw_images(owner, images):
    if not (SUPABASE_URL and SUPABASE_KEY):
        return {"success": False, "uploaded": [], "errors": ["Supabase Storage is not configured"], "message": "ยังไม่ได้ตั้งค่า Supabase Storage"}
    uploaded, errors, base = [], [], SUPABASE_URL.rstrip("/")
    for image in images:
        filename, encoded = image.get("filename", ""), image.get("data", "")
        if not filename or not encoded: continue
        try:
            payload = base64.b64decode(encoded)
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            response = requests.post(
                f"{base}/storage/v1/object/{BUCKET}/{quote(_path(owner, filename))}",
                headers=_headers({"Content-Type": content_type, "x-upsert": "true"}), data=payload, timeout=30,
            )
            if response.status_code in (200, 201): uploaded.append(filename)
            else: errors.append(f"{filename}: {response.text}")
        except Exception as exc: errors.append(f"{filename}: {exc}")
    if uploaded: threading.Thread(target=update_file_list, daemon=True).start()
    return {"success": bool(uploaded), "uploaded": uploaded, "errors": errors, "message": f"อัปโหลดสำเร็จ {len(uploaded)}/{len(images)} รูป"}


def upload_images_for_booking(booking_code, images, owner):
    normalized = []
    for index, image in enumerate(images, 1):
        filename = image.get("filename") or f"{booking_code}_{index}.webp"
        normalized.append({"filename": filename, "data": image.get("data", "")})
    return upload_raw_images(owner, normalized)


def delete_image_file(owner, filename):
    if not (SUPABASE_URL and SUPABASE_KEY): return {"success": False, "message": "ยังไม่ได้ตั้งค่า Supabase Storage"}
    try:
        response = requests.delete(
            f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{BUCKET}/{quote(_path(owner, filename))}",
            headers=_headers(), timeout=20,
        )
        if response.status_code in (200, 204):
            threading.Thread(target=update_file_list, daemon=True).start()
            return {"success": True, "message": "ลบไฟล์ออกจากคลังรูปภาพสำเร็จ"}
        return {"success": False, "message": f"ลบไฟล์ไม่สำเร็จ: {response.text}"}
    except Exception as exc:
        return {"success": False, "message": f"ลบไฟล์ไม่สำเร็จ: {exc}"}
