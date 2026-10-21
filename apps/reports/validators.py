"""Validators for files attached to reports."""

from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _

from apps.reports import constants

PDF_HEADER = b"%PDF-"
HEADER_SIZE = 1024
MAX_REPORT_PDF_SIZE = constants.MAX_REPORT_PDF_SIZE


def validate_report_pdf(file: UploadedFile) -> None:
    """Validate that ``file`` is a real PDF within the size limit.

    Args:
        file: The uploaded file to validate. Saved ``FieldFile`` values are
            ignored because they were validated when they were uploaded.

    Raises:
        ValidationError: If the extension, size or PDF header is invalid.
    """
    if not isinstance(file, UploadedFile):
        uploaded = getattr(file, "file", None)
        if not isinstance(uploaded, UploadedFile):
            return

    if Path(file.name).suffix.lower() != ".pdf":
        raise ValidationError(_("The file must be a PDF."))

    if file.size > MAX_REPORT_PDF_SIZE:
        raise ValidationError(
            _("The PDF exceeds the maximum size of %(size)s MB.")
            % {"size": MAX_REPORT_PDF_SIZE // (1024 * 1024)}
        )

    header = file.read(HEADER_SIZE)
    file.seek(0)
    if not header.startswith(PDF_HEADER):
        raise ValidationError(_("The file is not a valid PDF."))
