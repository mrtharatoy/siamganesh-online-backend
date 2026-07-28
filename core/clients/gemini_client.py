"""
Google Gemini generateContent API client (SG-B-201), extracted from
four call sites that each built the same URL pattern inline: app.py's
check_trending_news scheduler, core/blueprints/ai.py's debug_gemini
and ocr_image, and core/services/ai_service.py's
generate_thank_you_message. Different call sites use different API
versions (v1 vs v1beta) and models, so both are kept as parameters
rather than hardcoded, and the raw `requests.Response` is returned
unchanged so every caller's existing status_code/json()/headers
handling keeps working exactly as before.
"""
import requests

from config import GEMINI_API_KEY


def generate_content(model, payload, api_version="v1", timeout=15, headers=None):
    url = (
        f"https://generativelanguage.googleapis.com/{api_version}/models"
        f"/{model}:generateContent?key={GEMINI_API_KEY}"
    )
    kwargs = {"json": payload, "timeout": timeout}
    if headers is not None:
        kwargs["headers"] = headers
    return requests.post(url, **kwargs)
