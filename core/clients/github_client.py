"""
GitHub Contents API client (SG-B-201), extracted from the inline
`requests.get/put/delete` calls in core/blueprints/images.py.

Two GET-sha variants are kept distinct on purpose because the original
upload routes and the delete route queried slightly differently:
upload_image/upload_github_raw checked the current sha with a bare
contents URL (no `?ref=`), while delete_image's existence check used
an explicit `?ref={branch}`. Collapsing that into one function would
be a real (if probably harmless) behavior change, not a pure move.
"""
import requests

from config import GITHUB_USERNAME, REPO_NAME, BRANCH, GITHUB_TOKEN


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Siamganesh-Bot",
    }


def _contents_url(file_path, ref=None):
    url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{file_path}"
    if ref:
        url += f"?ref={ref}"
    return url


def get_file_sha(file_path, timeout=10):
    """Existing sha for file_path, or None. Matches the upload routes'
    original bare-URL (no ?ref=) existence check."""
    r = requests.get(_contents_url(file_path), headers=_headers(), timeout=timeout)
    if r.status_code == 200:
        return r.json().get("sha")
    return None


def get_file_sha_at_ref(file_path, ref, timeout=10):
    """Existing sha for file_path at a specific ref, and the raw status
    code, as (sha_or_None, status_code). Matches delete_image's original
    `?ref={branch}` existence check -- the caller's original "not found"
    message embeds this exact status code, so it can't be dropped."""
    r = requests.get(_contents_url(file_path, ref=ref), headers=_headers(), timeout=timeout)
    if r.status_code == 200:
        return r.json().get("sha"), r.status_code
    return None, r.status_code


def put_file(file_path, data_b64, message, branch=None, sha=None, timeout=30):
    """Create/update a file. Returns (success, error_message_or_None)."""
    payload = {
        "message": message,
        "content": data_b64,
        "branch": branch or BRANCH,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(_contents_url(file_path), headers=_headers(), json=payload, timeout=timeout)
    if r.status_code in (200, 201):
        return True, None
    return False, r.json().get("message", "unknown error")


def delete_file(file_path, sha, message, branch=None, timeout=30):
    """Delete a file. Returns (success, error_message_or_None)."""
    payload = {
        "message": message,
        "sha": sha,
        "branch": branch or BRANCH,
    }
    r = requests.delete(_contents_url(file_path), headers=_headers(), json=payload, timeout=timeout)
    if r.status_code in (200, 201):
        return True, None
    return False, r.json().get("message", "unknown error")
