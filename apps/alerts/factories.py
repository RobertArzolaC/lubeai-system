"""Factories for alerts models used in testing."""

import factory
from django.utils import timezone

from apps.alerts import models
from apps.equipment import factories as equipment_factories
from apps.reports import choices as report_choices
from apps.reports import factories as report_factories
from apps.users import factories as user_factories


class AlertFactory(factory.django.DjangoModelFactory):
    """Factory for creating Alert test instances."""

    class Meta:
        model = models.Alert

    report = factory.SubFactory(report_factories.ReportFactory)
    machine = factory.SubFactory(equipment_factories.MachineFactory)
    component = factory.SubFactory(equipment_factories.ComponentFactory)
    parameter = factory.Iterator(
        [choice[0] for choice in report_choices.Parameter.choices]
    )
    category = factory.Iterator(
        [choice[0] for choice in report_choices.Category.choices]
    )
    severity = factory.Iterator(["CRITICAL", "CAUTION", "WARNING"])
    status = "OPEN"
    value = factory.Faker("random_int", min=0, max=500)
    warning_limit = 75.0
    critical_limit = 100.0
    unit = "ppm"
    rule_type = "THRESHOLD"
    detected_at = factory.LazyFunction(timezone.now)
    dedup_key = factory.Sequence(lambda n: f"dedup-{n}")
    created_by = factory.SubFactory(user_factories.UserFactory)
    updated_by = factory.SelfAttribute("created_by")
