"""
Request-validation schemas (SG-H-101), one pydantic model per endpoint
that previously did its own manual `dict.get(...)`/`not X` checks
inline in the blueprint.

Design constraint: every route's error *response* (status code, JSON
shape, exact message) is completely unchanged by this refactor. These
schemas only replace the *mechanism* that decides whether the request
is valid -- each route still builds its own pre-existing error
response itself when validation fails, it just asks a schema instead
of repeating `if not x or not y: return jsonify(...), 400` inline.
That's why every model here raises a plain `ValueError` from a
validator (which pydantic wraps in its own `ValidationError`) rather
than trying to expose pydantic's own error format anywhere -- callers
only ever check "did this raise or not", never inspect *what* pydantic
says failed.

Each schema's docstring names the exact route it replaces and the
manual check it mirrors, so a diff against the blueprint's git history
is easy to audit.
"""
from typing import Optional

from pydantic import BaseModel, field_validator

PAGE_OWNERS = ("mahabucha", "muteteam", "muteteam_ceremony")


class SearchQuery(BaseModel):
    """GET /api/search -- mirrors: page must be one of PAGE_OWNERS,
    code must be non-empty after lower/strip."""

    page: str
    code: str

    @field_validator("page")
    @classmethod
    def _page_must_be_known_owner(cls, v):
        v = (v or "").lower()
        if v not in PAGE_OWNERS:
            raise ValueError("invalid page")
        return v

    @field_validator("code")
    @classmethod
    def _code_must_be_present(cls, v):
        v = (v or "").lower().strip()
        if not v:
            raise ValueError("code is required")
        return v


class GenerateMessageQuery(BaseModel):
    """GET /api/generate-message -- mirrors: booking_code must be
    non-empty after strip."""

    booking_code: str

    @field_validator("booking_code")
    @classmethod
    def _booking_code_must_be_present(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("booking_code is required")
        return v


class OcrImageBody(BaseModel):
    """POST /api/ocr-image -- mirrors: body.image must be present and
    truthy."""

    image: str

    @field_validator("image")
    @classmethod
    def _image_must_be_present(cls, v):
        if not v:
            raise ValueError("image is required")
        return v


class ListImagesQuery(BaseModel):
    """GET /api/images -- mirrors: page must be one of PAGE_OWNERS
    after lowercasing."""

    page: str

    @field_validator("page")
    @classmethod
    def _page_must_be_known_owner(cls, v):
        v = (v or "").lower()
        if v not in PAGE_OWNERS:
            raise ValueError("invalid page")
        return v


class UploadImageBody(BaseModel):
    """POST /api/upload-image -- mirrors: booking_code and images
    (non-empty list) required, owner optional (defaults to
    "muteteam", same as the original inline `.get("owner", "muteteam")`)."""

    booking_code: str
    images: list
    owner: str = "muteteam"

    @field_validator("booking_code")
    @classmethod
    def _booking_code_must_be_present(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("booking_code is required")
        return v

    @field_validator("images")
    @classmethod
    def _images_must_be_non_empty(cls, v):
        if not v:
            raise ValueError("images is required")
        return v

    @field_validator("owner")
    @classmethod
    def _owner_strip(cls, v):
        return (v or "muteteam").strip()


class UploadGithubRawBody(BaseModel):
    """POST /api/upload-github-raw -- mirrors: owner and images
    (non-empty list) required."""

    owner: str
    images: list

    @field_validator("owner")
    @classmethod
    def _owner_must_be_present(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("owner is required")
        return v

    @field_validator("images")
    @classmethod
    def _images_must_be_non_empty(cls, v):
        if not v:
            raise ValueError("images is required")
        return v


class DeleteImageBody(BaseModel):
    """POST /api/delete-image -- mirrors: page must be one of
    PAGE_OWNERS, filename must be non-empty."""

    page: str
    filename: str

    @field_validator("page")
    @classmethod
    def _page_must_be_known_owner(cls, v):
        v = (v or "").lower().strip()
        if v not in PAGE_OWNERS:
            raise ValueError("invalid page")
        return v

    @field_validator("filename")
    @classmethod
    def _filename_must_be_present(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("filename is required")
        return v


class SendFbMessageManualBody(BaseModel):
    """POST /api/send-fb-message-manual -- mirrors: owner and psid
    required, message/images optional (images defaults to [], same as
    the original inline `.get("images", [])`)."""

    owner: str
    psid: str
    message: Optional[str] = None
    images: list = []

    @field_validator("owner", "psid")
    @classmethod
    def _must_be_present(cls, v):
        if not v:
            raise ValueError("required")
        return v


class NotifyPhotoBody(BaseModel):
    """POST /api/notify-photo -- mirrors: owner and booking_code
    required; person1_name/person2_name/customer_name optional
    (default None); tray_count optional (defaults to 0, same as the
    original inline `.get("tray_count", 0)`)."""

    owner: str
    booking_code: str
    person1_name: Optional[str] = None
    person2_name: Optional[str] = None
    customer_name: Optional[str] = None
    tray_count: int = 0

    @field_validator("owner", "booking_code")
    @classmethod
    def _must_be_present(cls, v):
        if not v:
            raise ValueError("required")
        return v
