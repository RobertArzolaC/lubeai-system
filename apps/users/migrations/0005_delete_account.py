from django.db import migrations


def deactivate_removed_account_users(apps, schema_editor):
    """Deactivate users whose (soft-deleted) account had been removed."""
    account_model = apps.get_model("users", "Account")
    user_model = apps.get_model("users", "User")
    removed_user_ids = list(
        account_model.objects.filter(is_removed=True).values_list("user_id", flat=True)
    )
    if removed_user_ids:
        user_model.objects.filter(pk__in=removed_user_ids).update(is_active=False)


def reactivate_users(apps, schema_editor):
    """No-op reverse: the removed flag is gone, nothing to restore."""


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_role"),
    ]

    operations = [
        migrations.RunPython(deactivate_removed_account_users, reactivate_users),
        migrations.DeleteModel(name="Account"),
    ]
