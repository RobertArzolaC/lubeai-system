from django.db.models import QuerySet
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from apps.core import mixins as core_mixins
from apps.equipment import filtersets, forms, models


class MachineListView(core_mixins.BaseListView):
    model = models.Machine
    permission_required = "equipment.view_machine"
    filterset_class = filtersets.MachineFilter
    template_name = "equipment/machine/list.html"
    context_object_name = "machines"
    paginate_by = 5

    def get_queryset(self) -> QuerySet:
        """Return machines with related branch and fleet to avoid N+1 queries."""
        return models.Machine.objects.select_related("branch", "fleet")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Machine")
        context["entity_plural"] = _("Machines")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.equipment:machine_create")
        return context


class MachineDetailView(core_mixins.BaseDetailView):
    model = models.Machine
    permission_required = "equipment.view_machine"
    template_name = "equipment/machine/detail.html"
    context_object_name = "machine"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Machine")
        context["back_url"] = reverse_lazy("apps.equipment:machine_list")
        context["edit_url"] = reverse_lazy(
            "apps.equipment:machine_update", kwargs={"pk": self.object.pk}
        )
        context["components"] = self.object.components.select_related("type")
        return context


class MachineCreateView(core_mixins.BaseCreateView):
    model = models.Machine
    form_class = forms.MachineForm
    permission_required = "equipment.add_machine"
    template_name = "equipment/machine/form.html"
    success_message = _("Machine created successfully")
    success_url = reverse_lazy("apps.equipment:machine_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Machine")
        context["back_url"] = reverse_lazy("apps.equipment:machine_list")
        if self.request.POST:
            context["component_formset"] = forms.ComponentFormSet(self.request.POST)
        else:
            context["component_formset"] = forms.ComponentFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        component_formset = context["component_formset"]
        if component_formset.is_valid():
            self.object = form.save()
            component_formset.instance = self.object
            component_formset.save()
            return super().form_valid(form)
        return self.render_to_response(context)


class MachineUpdateView(core_mixins.BaseUpdateView):
    model = models.Machine
    form_class = forms.MachineForm
    permission_required = "equipment.change_machine"
    template_name = "equipment/machine/form.html"
    success_message = _("Machine updated successfully")
    success_url = reverse_lazy("apps.equipment:machine_list")
    context_object_name = "machine"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Machine")
        context["back_url"] = reverse_lazy("apps.equipment:machine_list")
        if self.request.POST:
            context["component_formset"] = forms.ComponentFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["component_formset"] = forms.ComponentFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        component_formset = context["component_formset"]
        if component_formset.is_valid():
            self.object = form.save()
            component_formset.instance = self.object
            component_formset.save()
            return super().form_valid(form)
        return self.render_to_response(context)


class MachineDeleteView(core_mixins.BaseDeleteView):
    model = models.Machine
    permission_required = "equipment.delete_machine"


class BranchListView(core_mixins.BaseListView):
    """View for listing branches with filtering and pagination."""

    model = models.Branch
    permission_required = "equipment.view_branch"
    filterset_class = filtersets.BranchFilter
    template_name = "equipment/branch/list.html"
    context_object_name = "branches"
    paginate_by = 10

    def get_queryset(self) -> QuerySet:
        """Return branches with location relations to avoid N+1 queries."""
        return models.Branch.objects.select_related(
            "country", "region", "subregion", "city"
        )

    def get_context_data(self, **kwargs: object) -> dict:
        """Add entity context variables."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Branch")
        context["entity_plural"] = _("Branches")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.equipment:branch_create")
        return context


class BranchDetailView(core_mixins.BaseDetailView):
    """View for displaying branch details including associated machines."""

    model = models.Branch
    permission_required = "equipment.view_branch"
    template_name = "equipment/branch/detail.html"
    context_object_name = "branch"

    def get_context_data(self, **kwargs: object) -> dict:
        """Add machines and navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Branch")
        context["back_url"] = reverse_lazy("apps.equipment:branch_list")
        context["edit_url"] = reverse_lazy(
            "apps.equipment:branch_update", kwargs={"pk": self.object.pk}
        )
        context["machines"] = self.object.machines.filter(
            is_active=True
        ).select_related("fleet")
        return context


class BranchCreateView(core_mixins.BaseCreateView):
    """View for creating a new branch."""

    model = models.Branch
    form_class = forms.BranchForm
    permission_required = "equipment.add_branch"
    template_name = "equipment/branch/form.html"
    success_message = _("Branch created successfully")
    success_url = reverse_lazy("apps.equipment:branch_list")

    def get_context_data(self, **kwargs: object) -> dict:
        """Add navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Branch")
        context["back_url"] = reverse_lazy("apps.equipment:branch_list")
        return context


class BranchUpdateView(core_mixins.BaseUpdateView):
    """View for updating an existing branch."""

    model = models.Branch
    form_class = forms.BranchForm
    permission_required = "equipment.change_branch"
    template_name = "equipment/branch/form.html"
    success_message = _("Branch updated successfully")
    success_url = reverse_lazy("apps.equipment:branch_list")
    context_object_name = "branch"

    def get_context_data(self, **kwargs: object) -> dict:
        """Add navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Branch")
        context["back_url"] = reverse_lazy("apps.equipment:branch_list")
        return context


class BranchDeleteView(core_mixins.BaseDeleteView):
    """View for deleting a branch."""

    model = models.Branch
    permission_required = "equipment.delete_branch"


class FleetListView(core_mixins.BaseListView):
    """View for listing fleets with filtering and pagination."""

    model = models.Fleet
    permission_required = "equipment.view_fleet"
    filterset_class = filtersets.FleetFilter
    template_name = "equipment/fleet/list.html"
    context_object_name = "fleets"
    paginate_by = 10

    def get_context_data(self, **kwargs: object) -> dict:
        """Add entity context variables."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Fleet")
        context["entity_plural"] = _("Fleets")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.equipment:fleet_create")
        return context


class FleetDetailView(core_mixins.BaseDetailView):
    """View for displaying fleet details including associated machines."""

    model = models.Fleet
    permission_required = "equipment.view_fleet"
    template_name = "equipment/fleet/detail.html"
    context_object_name = "fleet"

    def get_context_data(self, **kwargs: object) -> dict:
        """Add machines and navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Fleet")
        context["back_url"] = reverse_lazy("apps.equipment:fleet_list")
        context["edit_url"] = reverse_lazy(
            "apps.equipment:fleet_update", kwargs={"pk": self.object.pk}
        )
        context["machines"] = self.object.machines.filter(
            is_active=True
        ).select_related("branch")
        return context


class FleetCreateView(core_mixins.BaseCreateView):
    """View for creating a new fleet."""

    model = models.Fleet
    form_class = forms.FleetForm
    permission_required = "equipment.add_fleet"
    template_name = "equipment/fleet/form.html"
    success_message = _("Fleet created successfully")
    success_url = reverse_lazy("apps.equipment:fleet_list")

    def get_context_data(self, **kwargs: object) -> dict:
        """Add navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Fleet")
        context["back_url"] = reverse_lazy("apps.equipment:fleet_list")
        return context


class FleetUpdateView(core_mixins.BaseUpdateView):
    """View for updating an existing fleet."""

    model = models.Fleet
    form_class = forms.FleetForm
    permission_required = "equipment.change_fleet"
    template_name = "equipment/fleet/form.html"
    success_message = _("Fleet updated successfully")
    success_url = reverse_lazy("apps.equipment:fleet_list")
    context_object_name = "fleet"

    def get_context_data(self, **kwargs: object) -> dict:
        """Add navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Fleet")
        context["back_url"] = reverse_lazy("apps.equipment:fleet_list")
        return context


class FleetDeleteView(core_mixins.BaseDeleteView):
    """View for deleting a fleet."""

    model = models.Fleet
    permission_required = "equipment.delete_fleet"


class ComponentTypeListView(core_mixins.BaseListView):
    """View for listing component types with filtering and pagination."""

    model = models.ComponentType
    permission_required = "equipment.view_componenttype"
    filterset_class = filtersets.ComponentTypeFilter
    template_name = "equipment/component_type/list.html"
    context_object_name = "component_types"
    paginate_by = 10

    def get_context_data(self, **kwargs: object) -> dict:
        """Add entity context variables."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Component Type")
        context["entity_plural"] = _("Component Types")
        context["back_url"] = reverse_lazy("apps.dashboard:index")
        context["add_entity_url"] = reverse_lazy("apps.equipment:component_type_create")
        return context


class ComponentTypeDetailView(core_mixins.BaseDetailView):
    """View for displaying component type details including components."""

    model = models.ComponentType
    permission_required = "equipment.view_componenttype"
    template_name = "equipment/component_type/detail.html"
    context_object_name = "component_type"

    def get_context_data(self, **kwargs: object) -> dict:
        """Add components and navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Component Type")
        context["back_url"] = reverse_lazy("apps.equipment:component_type_list")
        context["edit_url"] = reverse_lazy(
            "apps.equipment:component_type_update", kwargs={"pk": self.object.pk}
        )
        context["components"] = self.object.components.filter(
            is_active=True
        ).select_related("machine")
        return context


class ComponentTypeCreateView(core_mixins.BaseCreateView):
    """View for creating a new component type."""

    model = models.ComponentType
    form_class = forms.ComponentTypeForm
    permission_required = "equipment.add_componenttype"
    template_name = "equipment/component_type/form.html"
    success_message = _("Component type created successfully")
    success_url = reverse_lazy("apps.equipment:component_type_list")

    def get_context_data(self, **kwargs: object) -> dict:
        """Add navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Component Type")
        context["back_url"] = reverse_lazy("apps.equipment:component_type_list")
        return context


class ComponentTypeUpdateView(core_mixins.BaseUpdateView):
    """View for updating an existing component type."""

    model = models.ComponentType
    form_class = forms.ComponentTypeForm
    permission_required = "equipment.change_componenttype"
    template_name = "equipment/component_type/form.html"
    success_message = _("Component type updated successfully")
    success_url = reverse_lazy("apps.equipment:component_type_list")
    context_object_name = "component_type"

    def get_context_data(self, **kwargs: object) -> dict:
        """Add navigation context."""
        context = super().get_context_data(**kwargs)
        context["entity"] = _("Component Type")
        context["back_url"] = reverse_lazy("apps.equipment:component_type_list")
        return context


class ComponentTypeDeleteView(core_mixins.BaseDeleteView):
    """View for deleting a component type."""

    model = models.ComponentType
    permission_required = "equipment.delete_componenttype"
