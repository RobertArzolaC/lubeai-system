"""Attach a dummy PDF to reports that do not have one."""

from typing import Any

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q

from apps.reports import models
from apps.reports.services.dummy_pdf import build_dummy_report_pdf


class Command(BaseCommand):
    """Fill empty report PDF fields with a placeholder document."""

    help = "Attach a dummy PDF to reports without a PDF file"

    def add_arguments(self, parser: CommandParser) -> None:
        """Register the command options.

        Args:
            parser: The command's argument parser.
        """
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing PDFs as well.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Process at most this many reports.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Generate and store a dummy PDF for each matching report.

        Args:
            *args: Unused positional arguments.
            **options: Parsed management options.
        """
        queryset = models.Report.objects.only("pk", "lab_number", "pdf_file")
        if not options["overwrite"]:
            queryset = queryset.filter(Q(pdf_file="") | Q(pdf_file__isnull=True))
        queryset = queryset.order_by("pk")
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        updated = 0
        for report in queryset:
            report.pdf_file.save(
                f"{report.lab_number}.pdf",
                ContentFile(build_dummy_report_pdf(report.lab_number)),
                save=True,
            )
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"{updated} reports updated with a dummy PDF.")
        )
