"""
Centralized error handlers (SG-B-107).

Before this, app.py had no custom @app.errorhandler at all: an
unmatched route or an unhandled exception fell through to Flask's
default HTML error pages (verified directly against a running
instance before writing this -- 404 and 500 both returned
`text/html; charset=utf-8` with Flask's stock boilerplate body, no
traceback leak since debug=False in production).

Adding a JSON shape here for these two cases is a deliberate, approved
behavior change (confirmed with the project owner), not an incidental
one bundled into the SG-B-102..106 structural moves -- those preserved
every route's own explicit error responses exactly as they were.
Nothing in this file changes any route's own try/except error
handling; it only replaces the *default* fallback for the two cases
no route ever handled itself.
"""
from flask import jsonify


def register_error_handlers(app):
    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def handle_server_error(error):
        app.logger.exception("Unhandled error")
        return jsonify({"error": "internal server error"}), 500
