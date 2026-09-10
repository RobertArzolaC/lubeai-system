"""Rendering tests for the real equipment and dashboard templates."""

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.equipment.factories import (
    BranchFactory,
    ComponentTypeFactory,
    FleetFactory,
    MachineFactory,
)
from apps.users.factories import UserFactory


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given equipment permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="equipment",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)


class EquipmentTemplateRenderingTests(TestCase):
    """Render the real equipment templates to catch syntax and wiring errors."""

    def setUp(self) -> None:
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        self.machine = MachineFactory()
        self.branch = BranchFactory()
        self.fleet = FleetFactory()
        self.component_type = ComponentTypeFactory()

    def test_list_templates_render(self) -> None:
        """Every equipment list template renders successfully."""
        for name in (
            "machine_list",
            "branch_list",
            "fleet_list",
            "component_type_list",
        ):
            with self.subTest(view=name):
                response = self.client.get(reverse(f"apps.equipment:{name}"))
                self.assertEqual(response.status_code, 200)

    def test_detail_templates_render(self) -> None:
        """Every equipment detail template renders successfully."""
        cases = {
            "machine_detail": self.machine.pk,
            "branch_detail": self.branch.pk,
            "fleet_detail": self.fleet.pk,
            "component_type_detail": self.component_type.pk,
        }
        for name, pk in cases.items():
            with self.subTest(view=name):
                response = self.client.get(
                    reverse(f"apps.equipment:{name}", kwargs={"pk": pk})
                )
                self.assertEqual(response.status_code, 200)

    def test_create_templates_render(self) -> None:
        """Every equipment create form template renders successfully."""
        for name in (
            "machine_create",
            "branch_create",
            "fleet_create",
            "component_type_create",
        ):
            with self.subTest(view=name):
                response = self.client.get(reverse(f"apps.equipment:{name}"))
                self.assertEqual(response.status_code, 200)

    def test_update_templates_render(self) -> None:
        """Every equipment update form template renders successfully."""
        cases = {
            "machine_update": self.machine.pk,
            "branch_update": self.branch.pk,
            "fleet_update": self.fleet.pk,
            "component_type_update": self.component_type.pk,
        }
        for name, pk in cases.items():
            with self.subTest(view=name):
                response = self.client.get(
                    reverse(f"apps.equipment:{name}", kwargs={"pk": pk})
                )
                self.assertEqual(response.status_code, 200)

    def test_machine_form_contains_dynamic_formset(self) -> None:
        """The machine form exposes the formset management data and template."""
        response = self.client.get(reverse("apps.equipment:machine_create"))
        self.assertContains(response, "components-TOTAL_FORMS")
        self.assertContains(response, "empty-form-template")
        self.assertContains(response, "add-component-row")

    def test_branch_form_loads_select2_assets(self) -> None:
        """The branch form includes the jQuery/Select2 assets DAL needs."""
        response = self.client.get(reverse("apps.equipment:branch_create"))
        self.assertContains(response, "admin/js/vendor/jquery/jquery.min.js")
        self.assertContains(response, "admin/js/vendor/select2/select2")
        self.assertContains(response, "autocomplete_light/select2")
        self.assertContains(response, "css/select2-custom.css")

    def test_branch_form_uses_default_select2_theme(self) -> None:
        """The location widgets use the default Select2 theme, not bootstrap5."""
        response = self.client.get(reverse("apps.equipment:branch_create"))
        self.assertContains(response, 'data-theme="default"')
        self.assertNotContains(response, "bootstrap5")
        self.assertNotContains(response, "form-select")


class DashboardModuleAccessTests(TestCase):
    """Permission-gated equipment links inside the dashboard."""

    def setUp(self) -> None:
        cache.clear()

    def test_dashboard_shows_equipment_links_for_authorized_user(self) -> None:
        """A superuser sees every equipment module link."""
        user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("apps.equipment:machine_list"))
        self.assertContains(response, reverse("apps.equipment:branch_list"))
        self.assertContains(response, reverse("apps.equipment:fleet_list"))
        self.assertContains(response, reverse("apps.equipment:component_type_list"))

    def test_dashboard_hides_equipment_links_without_permission(self) -> None:
        """A user without permissions does not see the equipment module links."""
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("apps.equipment:machine_list"))
        self.assertNotContains(response, reverse("apps.equipment:branch_list"))
        self.assertNotContains(response, reverse("apps.equipment:fleet_list"))
        self.assertNotContains(response, reverse("apps.equipment:component_type_list"))


class EquipmentRowPermissionGatingTests(TestCase):
    """Action buttons in list rows are gated by Django permissions."""

    def setUp(self) -> None:
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.fleet = FleetFactory()
        self.list_url = reverse("apps.equipment:fleet_list")
        self.detail_url = reverse(
            "apps.equipment:fleet_detail", kwargs={"pk": self.fleet.pk}
        )
        self.update_url = reverse(
            "apps.equipment:fleet_update", kwargs={"pk": self.fleet.pk}
        )
        self.delete_url = reverse(
            "apps.equipment:fleet_delete", kwargs={"pk": self.fleet.pk}
        )

    def test_view_only_shows_detail_and_hides_write_actions(self) -> None:
        """A view-only user sees the detail action but no edit/delete."""
        grant_permissions(self.user, "view_fleet")
        response = self.client.get(self.list_url)
        self.assertContains(response, self.detail_url)
        self.assertNotContains(response, self.update_url)
        self.assertNotContains(response, self.delete_url)

    def test_change_permission_shows_edit_action(self) -> None:
        """The change permission reveals the edit action."""
        grant_permissions(self.user, "view_fleet", "change_fleet")
        response = self.client.get(self.list_url)
        self.assertContains(response, self.update_url)

    def test_delete_permission_shows_delete_action(self) -> None:
        """The delete permission reveals the delete action."""
        grant_permissions(self.user, "view_fleet", "delete_fleet")
        response = self.client.get(self.list_url)
        self.assertContains(response, self.delete_url)

    def test_add_permission_shows_create_button(self) -> None:
        """The add permission reveals the create button."""
        grant_permissions(self.user, "view_fleet", "add_fleet")
        response = self.client.get(self.list_url)
        self.assertContains(response, reverse("apps.equipment:fleet_create"))

    def test_without_add_permission_hides_create_button(self) -> None:
        """Without the add permission the create button is hidden."""
        grant_permissions(self.user, "view_fleet")
        response = self.client.get(self.list_url)
        self.assertNotContains(response, reverse("apps.equipment:fleet_create"))
