from django.contrib.auth.models import Group
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.users import models


@receiver(post_delete, sender=models.Role)
def remove_role_group(sender, instance, **kwargs):
    """Delete the backing group when a role is removed directly."""
    if instance.group_id is not None:
        Group.objects.filter(pk=instance.group_id).delete()
