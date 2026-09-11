from django.db import migrations

# Severity ranking used to keep the worst alert per report.
_SEVERITY_RANK = {
    "CRITICAL": 3,
    "CAUTION": 2,
    "WARNING": 1,
}


def consolidate_alerts_per_report(apps, schema_editor):
    """Keep one alert per report before the report-level refactor.

    For every report with more than one alert, keeps the most severe one
    (breaking ties by the most recent detection) and deletes the rest. The
    surviving alert receives the new report-level ``dedup_key``. Alerts with
    no report are preserved untouched.
    """
    alert_model = apps.get_model("alerts", "Alert")
    report_ids = (
        alert_model.objects.exclude(report__isnull=True)
        .values_list("report_id", flat=True)
        .distinct()
    )
    for report_id in report_ids:
        alerts = list(
            alert_model.objects.filter(report_id=report_id).order_by(
                "-detected_at", "-created", "-id"
            )
        )
        if not alerts:
            continue
        winner = max(alerts, key=lambda alert: _SEVERITY_RANK.get(alert.severity, 0))
        winner.dedup_key = f"{report_id}:THRESHOLD"
        winner.save(update_fields=["dedup_key"])
        alert_model.objects.filter(report_id=report_id).exclude(pk=winner.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("alerts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            consolidate_alerts_per_report,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
