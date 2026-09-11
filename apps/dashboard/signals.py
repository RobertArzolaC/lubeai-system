"""Invalidate the cached dashboard payload when its source data changes."""

from django.db.models.signals import post_delete, post_save

from apps.alerts import models as alerts_models
from apps.dashboard import cache as dashboard_cache
from apps.equipment import models as equipment_models
from apps.reports import models as reports_models

INVALIDATION_MODELS = (
    reports_models.Report,
    reports_models.LabAnalysis,
    reports_models.AnalysisThreshold,
    alerts_models.Alert,
    equipment_models.Machine,
    equipment_models.Fleet,
    equipment_models.ComponentType,
)


def invalidate_dashboard_cache(sender, **kwargs) -> None:
    """Bump the dashboard cache version on any watched write."""
    dashboard_cache.bump_cache_version()


for model in INVALIDATION_MODELS:
    label = model._meta.label_lower
    post_save.connect(
        invalidate_dashboard_cache,
        sender=model,
        dispatch_uid=f"dashboard.cache.post_save.{label}",
    )
    post_delete.connect(
        invalidate_dashboard_cache,
        sender=model,
        dispatch_uid=f"dashboard.cache.post_delete.{label}",
    )
