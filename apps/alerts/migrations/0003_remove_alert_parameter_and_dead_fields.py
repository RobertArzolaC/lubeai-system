from django.conf import settings
from django.db import migrations, models


class SetLockTimeout(migrations.RunSQL):
    """Set a statement lock timeout only on PostgreSQL.

    ``SET LOCAL lock_timeout`` is PostgreSQL-specific; running it against other
    backends (e.g. SQLite used by the test runner) raises a syntax error.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state) -> None:
        """Apply the statement only when the active backend is PostgreSQL."""
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(
        self, app_label, schema_editor, from_state, to_state
    ) -> None:
        """Reverse the statement only when the active backend is PostgreSQL."""
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0002_data_consolidate_alerts_per_report"),
        ("equipment", "0001_initial"),
        ("reports", "0002_alter_report_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        SetLockTimeout(
            "SET LOCAL lock_timeout = '2s'",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RemoveIndex(
            model_name="alert",
            name="alerts_aler_machine_fc162d_idx",
        ),
        migrations.AddIndex(
            model_name="alert",
            index=models.Index(
                fields=["machine", "detected_at"], name="alerts_aler_machine_2de50e_idx"
            ),
        ),
        migrations.RemoveField(
            model_name="alert",
            name="parameter",
        ),
        migrations.RemoveField(
            model_name="alert",
            name="rule_type",
        ),
        migrations.RemoveField(
            model_name="alert",
            name="sent_channels",
        ),
    ]
