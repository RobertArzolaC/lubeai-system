import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.users import models

logger = logging.getLogger(__name__)


@receiver(post_save, sender=models.User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        try:
            models.Account.objects.create(user=instance)
            logger.info(
                f"Cuenta creada automáticamente para el usuario: {instance.email}"
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"Error al crear cuenta para el usuario {instance.email}: {e!s}"
            )


########################################
# Migrated from customers app
########################################


@receiver(post_delete, sender=models.Account)
def remove_account_user(sender, instance, **kwargs):
    user = instance.user
    user.delete()
