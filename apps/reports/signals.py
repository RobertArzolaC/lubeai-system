"""File lifecycle signals for report PDFs."""

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.reports import models


@receiver(
    pre_save,
    sender=models.Report,
    dispatch_uid="reports.remember_old_pdf",
)
def remember_old_pdf(sender, instance: models.Report, **kwargs) -> None:
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
    sender, instance: models.Report, created: bool, **kwargs
) -> None:
    """Delete the previous PDF after a replacement is persisted.

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
        instance.pdf_file.storage.delete(old_name)


@receiver(
    post_delete,
    sender=models.Report,
    dispatch_uid="reports.delete_pdf",
)
def delete_pdf(sender, instance: models.Report, **kwargs) -> None:
    """Delete the stored PDF when the report is removed.

    Args:
        sender: The report model class.
        instance: The deleted report.
    """
    if instance.pdf_file:
        instance.pdf_file.delete(save=False)
