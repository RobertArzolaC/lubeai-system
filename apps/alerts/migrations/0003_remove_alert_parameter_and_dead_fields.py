from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0002_data_consolidate_alerts_per_report"),
        ("equipment", "0001_initial"),
        ("reports", "0002_alter_report_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunSQL(
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
