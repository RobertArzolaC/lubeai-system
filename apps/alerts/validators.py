"""Validators for the files attached to an alert status change."""

from pathlib import Path
from typing import Final

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _

ALLOWED_ATTACHMENT_EXTENSIONS: Final[tuple[str, ...]] = (
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
)
ATTACHMENT_ACCEPT: Final[str] = ",".join(ALLOWED_ATTACHMENT_EXTENSIONS)

# Maximum size accepted for a status attachment (10 MB).
MAX_ALERT_ATTACHMENT_SIZE: Final[int] = 10 * 1024 * 1024

# Maximum length accepted for the optional description of a status change.
MAX_ALERT_NOTE_LENGTH: Final[int] = 1000

_HEADER_SIZE: Final[int] = 16
_PDF_HEADER: Final[bytes] = b"%PDF-"
_PNG_HEADER: Final[bytes] = b"\x89PNG\r\n\x1a\n"
_JPEG_HEADER: Final[bytes] = b"\xff\xd8\xff"
_RIFF_HEADER: Final[bytes] = b"RIFF"
_WEBP_HEADER: Final[bytes] = b"WEBP"


def _has_valid_signature(header: bytes, suffix: str) -> bool:
    """Return whether ``header`` matches the signature of ``suffix``.

    Args:
        header: First bytes read from the uploaded file.
        suffix: Lower-cased file extension, including the dot.

    Returns:
        ``True`` when the binary content matches the declared file type.
    """
    if suffix == ".pdf":
        return header.startswith(_PDF_HEADER)
    if suffix == ".png":
        return header.startswith(_PNG_HEADER)
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(_JPEG_HEADER)
    if suffix == ".webp":
        return header.startswith(_RIFF_HEADER) and header[8:12] == _WEBP_HEADER
    return False


def validate_alert_attachment(file: UploadedFile) -> None:
    """Validate that ``file`` is a PDF or image within the size limit.

    Args:
        file: The uploaded file to validate. Saved ``FieldFile`` values are
            ignored because they were validated when they were uploaded.

    Raises:
        ValidationError: If the extension, size or binary signature is invalid.
    """
    if not isinstance(file, UploadedFile):
        uploaded = getattr(file, "file", None)
        if not isinstance(uploaded, UploadedFile):
            return

    suffix = Path(file.name).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError(
            _("The attachment must be a PDF or an image (PNG, JPG or WEBP).")
        )

    if file.size > MAX_ALERT_ATTACHMENT_SIZE:
        raise ValidationError(
            _("The attachment exceeds the maximum size of %(size)s MB.")
            % {"size": MAX_ALERT_ATTACHMENT_SIZE // (1024 * 1024)}
        )

    header = file.read(_HEADER_SIZE)
    file.seek(0)
    if not _has_valid_signature(header, suffix):
        raise ValidationError(_("The attachment is not a valid PDF or image."))
