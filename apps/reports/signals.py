"""File lifecycle signals for report PDFs."""

import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.reports import models

logger = logging.getLogger(__name__)


@receiver(
    pre_save,
    sender=models.Report,
    dispatch_uid="reports.remember_old_pdf",
)
def remember_old_pdf(
    sender: type[models.Report], instance: models.Report, **kwargs
) -> None:
    """Keep the stored PDF name so a replacement can remove the old file.

    Args:
        sender: The report model class.
        instance: The report being saved.
    """
    if instance.pk:
        instance._old_pdf_name = (
            sender.objects.filter(pk=instance.pk)
            .values_list("pdf_file", flat=True)
            .first()
        )


@receiver(
    post_save,
    sender=models.Report,
    dispatch_uid="reports.delete_replaced_pdf",
)
def delete_replaced_pdf(
    sender: type[models.Report],
    instance: models.Report,
    created: bool,
    **kwargs,
) -> None:
    """Delete the previous PDF after a replacement is committed.

    Args:
        sender: The report model class.
        instance: The saved report.
        created: Whether the report was just created.
    """
    if created:
        return
    old_name = getattr(instance, "_old_pdf_name", None)
    new_name = instance.pdf_file.name if instance.pdf_file else ""
    if old_name and old_name != new_name:
        storage = instance.pdf_file.storage

        def delete_old_file() -> None:
            try:
                storage.delete(old_name)
            except OSError:
                logger.exception("Could not delete replaced report PDF %s", old_name)

        transaction.on_commit(delete_old_file)


@receiver(
    post_delete,
    sender=models.Report,
    dispatch_uid="reports.delete_pdf",
)
def delete_pdf(sender: type[models.Report], instance: models.Report, **kwargs) -> None:
    """Delete the stored PDF when the report is committed as deleted.

    Args:
        sender: The report model class.
        instance: The deleted report.
    """
    if not instance.pdf_file:
        return
    storage = instance.pdf_file.storage
    file_name = instance.pdf_file.name

    def delete_file() -> None:
        try:
            storage.delete(file_name)
        except OSError:
            logger.exception("Could not delete report PDF %s", file_name)

    transaction.on_commit(delete_file)
