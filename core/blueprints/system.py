"""
Search/System blueprint (SG-B-106), extracted from app.py:
`/api/search`, `/api/system-status`. Route logic is unchanged from the
original app.py handlers of the same name.

system_status()'s business logic (DB health check, Supabase storage
stats, response assembly) moved to core/services/system_status_service.py
and core/repositories/system_status_repository.py (SG-B-202), so this
route is now just: build the response via the service, jsonify it.

The server start time is read via `flask.current_app` rather than a direct
`app` import, to avoid a
circular import back to app.py (see git history for the SG-B-106
commit message for the full explanation of that pattern).
"""
from flask import Blueprint, request, jsonify, current_app
from pydantic import ValidationError

from core.schemas import SearchQuery
from core.services.image_cache_service import CACHED_FILES, lock, is_loaded, update_file_list, get_image_url
from core.services.system_status_service import build_system_status

system_bp = Blueprint("system", __name__)


@system_bp.route('/api/search', methods=['GET'])
def search_api():
    try:
        query = SearchQuery(page=request.args.get('page', ''), code=request.args.get('code', ''))
    except ValidationError:
        return jsonify({"found": False, "message": "ข้อมูลไม่ครบ"}), 400
    page, code = query.page, query.code

    if not is_loaded():
        with lock:
            if not is_loaded():
                update_file_list()

    current_cache = CACHED_FILES.get(page, {})

    if page == "muteteam":
        matched = [
            {"code": key.upper(), "image_url": get_image_url(page, filename)}
            for key, filename in sorted(current_cache.items())
            if key.startswith(code)
        ]
        if matched:
            return jsonify({"found": True, "results": matched, "count": len(matched)}), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404
    else:
        if code in current_cache:
            return jsonify({
                "found": True,
                "code": code.upper(),
                "image_url": get_image_url(page, current_cache[code])
            }), 200
        return jsonify({"found": False, "message": "ไม่พบรูปภาพ"}), 404


@system_bp.route('/api/system-status', methods=['GET'])
def system_status():
    return jsonify(build_system_status(current_app)), 200
