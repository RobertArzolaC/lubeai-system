"""Tests for the ``apps.equipment.views`` module."""

from django.conf import settings
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.equipment import factories, forms, models, views
from apps.users import factories as users_factories

EQUIPMENT_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [settings.BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.locmem.Loader",
                    {
                        "equipment/machine/list.html": "",
                        "equipment/machine/detail.html": "",
                        "equipment/machine/form.html": "",
                        "equipment/branch/list.html": "",
                        "equipment/branch/detail.html": "",
                        "equipment/branch/form.html": "",
                        "equipment/fleet/list.html": "",
                        "equipment/fleet/detail.html": "",
                        "equipment/fleet/form.html": "",
                        "equipment/component_type/list.html": "",
                        "equipment/component_type/detail.html": "",
                        "equipment/component_type/form.html": "",
                    },
                ),
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "constance.context_processors.config",
                "apps.core.context_processors.site_processor",
            ],
        },
    }
]


def grant_permissions(user, *codenames: str) -> None:
    """Grant the given equipment permission codenames to ``user``."""
    permissions = Permission.objects.filter(
        content_type__app_label="equipment",
        codename__in=codenames,
    )
    user.user_permissions.add(*permissions)


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class FleetListViewTests(TestCase):
    """Tests for :class:`FleetListView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.fleet = factories.FleetFactory(name="North Fleet")
        self.url = reverse("apps.equipment:fleet_list")

    def test_anonymous_user_redirected_to_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_lists_fleets(self) -> None:
        """Users with the view permission can list fleets."""
        grant_permissions(self.user, "view_fleet")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "equipment/fleet/list.html")
        self.assertIn(self.fleet, response.context["fleets"])

    def test_list_filters_by_name(self) -> None:
        """The list applies the ``name_search`` filter."""
        other = factories.FleetFactory(name="South Fleet")
        grant_permissions(self.user, "view_fleet")
        self.client.force_login(self.user)
        response = self.client.get(self.url, {"name_search": "North"})
        self.assertIn(self.fleet, response.context["fleets"])
        self.assertNotIn(other, response.context["fleets"])


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class FleetDetailViewTests(TestCase):
    """Tests for :class:`FleetDetailView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.fleet = factories.FleetFactory()
        self.url = reverse("apps.equipment:fleet_detail", kwargs={"pk": self.fleet.pk})

    def test_anonymous_user_redirected_to_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_sees_detail(self) -> None:
        """Users with the view permission can see fleet details."""
        grant_permissions(self.user, "view_fleet")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "equipment/fleet/detail.html")
        self.assertEqual(response.context["fleet"], self.fleet)


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class FleetCreateViewTests(TestCase):
    """Tests for :class:`FleetCreateView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.url = reverse("apps.equipment:fleet_create")

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_opens_form(self) -> None:
        """Users with the add permission can open the create form."""
        grant_permissions(self.user, "add_fleet")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "equipment/fleet/form.html")

    def test_post_creates_fleet(self) -> None:
        """A valid post creates the fleet and stamps the author."""
        grant_permissions(self.user, "add_fleet")
        self.client.force_login(self.user)
        response = self.client.post(self.url, {"name": "West Fleet", "is_active": True})
        self.assertRedirects(
            response,
            reverse("apps.equipment:fleet_list"),
            fetch_redirect_response=False,
        )
        fleet = models.Fleet.objects.get(name="West Fleet")
        self.assertEqual(fleet.created_by, self.user)
        self.assertEqual(fleet.updated_by, self.user)


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class FleetUpdateViewTests(TestCase):
    """Tests for :class:`FleetUpdateView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.fleet = factories.FleetFactory(name="North Fleet")
        self.url = reverse("apps.equipment:fleet_update", kwargs={"pk": self.fleet.pk})

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_opens_form(self) -> None:
        """Users with the change permission can open the update form."""
        grant_permissions(self.user, "change_fleet")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["fleet"], self.fleet)

    def test_post_updates_fleet(self) -> None:
        """A valid post updates the fleet."""
        grant_permissions(self.user, "change_fleet")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url, {"name": "Renamed Fleet", "is_active": True}
        )
        self.assertRedirects(
            response,
            reverse("apps.equipment:fleet_list"),
            fetch_redirect_response=False,
        )
        self.fleet.refresh_from_db()
        self.assertEqual(self.fleet.name, "Renamed Fleet")


class FleetDeleteViewTests(TestCase):
    """Tests for :class:`FleetDeleteView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.fleet = factories.FleetFactory()

    def delete_url(self, pk: int) -> str:
        """Return the delete URL for the given fleet pk."""
        return reverse("apps.equipment:fleet_delete", kwargs={"pk": pk})

    def test_anonymous_user_gets_json_403(self) -> None:
        """Anonymous delete attempts receive a JSON 403 response."""
        response = self.client.post(self.delete_url(self.fleet.pk))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "error")

    def test_user_without_permission_gets_json_403(self) -> None:
        """Authenticated users without permission get a JSON 403 response."""
        self.client.force_login(self.user)
        response = self.client.post(self.delete_url(self.fleet.pk))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "error")

    def test_delete_fleet_success(self) -> None:
        """Authorized users can delete a fleet."""
        grant_permissions(self.user, "delete_fleet")
        self.client.force_login(self.user)
        response = self.client.post(self.delete_url(self.fleet.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertFalse(models.Fleet.objects.filter(pk=self.fleet.pk).exists())

    def test_delete_missing_fleet_returns_json_404(self) -> None:
        """Deleting a non-existing fleet returns a JSON 404 response."""
        grant_permissions(self.user, "delete_fleet")
        self.client.force_login(self.user)
        response = self.client.post(self.delete_url(999999))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "error")


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class ComponentTypeListViewTests(TestCase):
    """Tests for :class:`ComponentTypeListView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.component_type = factories.ComponentTypeFactory(name="Pump")
        self.url = reverse("apps.equipment:component_type_list")

    def test_anonymous_user_redirected_to_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_lists_component_types(self) -> None:
        """Users with the view permission can list component types."""
        grant_permissions(self.user, "view_componenttype")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "equipment/component_type/list.html")
        self.assertIn(self.component_type, response.context["component_types"])

    def test_list_filters_by_name(self) -> None:
        """The list applies the ``name_search`` filter."""
        other = factories.ComponentTypeFactory(name="Motor")
        grant_permissions(self.user, "view_componenttype")
        self.client.force_login(self.user)
        response = self.client.get(self.url, {"name_search": "Pump"})
        self.assertIn(self.component_type, response.context["component_types"])
        self.assertNotIn(other, response.context["component_types"])


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class ComponentTypeDetailViewTests(TestCase):
    """Tests for :class:`ComponentTypeDetailView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.component_type = factories.ComponentTypeFactory()
        self.url = reverse(
            "apps.equipment:component_type_detail",
            kwargs={"pk": self.component_type.pk},
        )

    def test_anonymous_user_redirected_to_login(self) -> None:
        """Anonymous users are redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_sees_detail(self) -> None:
        """Users with the view permission can see component type details."""
        grant_permissions(self.user, "view_componenttype")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "equipment/component_type/detail.html")
        self.assertEqual(response.context["component_type"], self.component_type)


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class ComponentTypeCreateViewTests(TestCase):
    """Tests for :class:`ComponentTypeCreateView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.url = reverse("apps.equipment:component_type_create")

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_opens_form(self) -> None:
        """Users with the add permission can open the create form."""
        grant_permissions(self.user, "add_componenttype")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "equipment/component_type/form.html")

    def test_post_creates_component_type(self) -> None:
        """A valid post creates the component type and stamps the author."""
        grant_permissions(self.user, "add_componenttype")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"name": "Compressor", "description": "Air compressor", "is_active": True},
        )
        self.assertRedirects(
            response,
            reverse("apps.equipment:component_type_list"),
            fetch_redirect_response=False,
        )
        component_type = models.ComponentType.objects.get(name="Compressor")
        self.assertEqual(component_type.created_by, self.user)
        self.assertEqual(component_type.updated_by, self.user)


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class ComponentTypeUpdateViewTests(TestCase):
    """Tests for :class:`ComponentTypeUpdateView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.component_type = factories.ComponentTypeFactory(name="Pump")
        self.url = reverse(
            "apps.equipment:component_type_update",
            kwargs={"pk": self.component_type.pk},
        )

    def test_user_without_permission_forbidden(self) -> None:
        """Authenticated users without permission get a 403 response."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_user_with_permission_opens_form(self) -> None:
        """Users with the change permission can open the update form."""
        grant_permissions(self.user, "change_componenttype")
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["component_type"], self.component_type)

    def test_post_updates_component_type(self) -> None:
        """A valid post updates the component type."""
        grant_permissions(self.user, "change_componenttype")
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"name": "Renamed Type", "description": "Updated", "is_active": True},
        )
        self.assertRedirects(
            response,
            reverse("apps.equipment:component_type_list"),
            fetch_redirect_response=False,
        )
        self.component_type.refresh_from_db()
        self.assertEqual(self.component_type.name, "Renamed Type")


class ComponentTypeDeleteViewTests(TestCase):
    """Tests for :class:`ComponentTypeDeleteView`."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.component_type = factories.ComponentTypeFactory()

    def delete_url(self, pk: int) -> str:
        """Return the delete URL for the given component type pk."""
        return reverse("apps.equipment:component_type_delete", kwargs={"pk": pk})

    def test_anonymous_user_gets_json_403(self) -> None:
        """Anonymous delete attempts receive a JSON 403 response."""
        response = self.client.post(self.delete_url(self.component_type.pk))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "error")

    def test_user_without_permission_gets_json_403(self) -> None:
        """Authenticated users without permission get a JSON 403 response."""
        self.client.force_login(self.user)
        response = self.client.post(self.delete_url(self.component_type.pk))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["status"], "error")

    def test_delete_component_type_success(self) -> None:
        """Authorized users can delete a component type."""
        grant_permissions(self.user, "delete_componenttype")
        self.client.force_login(self.user)
        response = self.client.post(self.delete_url(self.component_type.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertFalse(
            models.ComponentType.objects.filter(pk=self.component_type.pk).exists()
        )

    def test_delete_missing_component_type_returns_json_404(self) -> None:
        """Deleting a non-existing component type returns a JSON 404 response."""
        grant_permissions(self.user, "delete_componenttype")
        self.client.force_login(self.user)
        response = self.client.post(self.delete_url(999999))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "error")


@override_settings(TEMPLATES=EQUIPMENT_TEMPLATES)
class MachineAndBranchViewTests(TestCase):
    """Regression tests for the existing Machine and Branch views."""

    def setUp(self) -> None:
        self.user = users_factories.UserFactory()
        self.machine = factories.MachineFactory()
        self.branch = factories.BranchFactory()

    def test_machine_detail_renders(self) -> None:
        """The machine detail view fetches the object and renders."""
        grant_permissions(self.user, "view_machine")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.equipment:machine_detail", kwargs={"pk": self.machine.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["machine"], self.machine)

    def test_machine_create_form_renders(self) -> None:
        """The machine form no longer receives an unexpected ``user`` kwarg."""
        grant_permissions(self.user, "add_machine")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.equipment:machine_create"))
        self.assertEqual(response.status_code, 200)

    def test_machine_delete_requires_permission(self) -> None:
        """The machine delete view returns JSON 403 without permission."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.equipment:machine_delete", kwargs={"pk": self.machine.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_branch_detail_renders(self) -> None:
        """The branch detail view fetches the object and renders."""
        grant_permissions(self.user, "view_branch")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.equipment:branch_detail", kwargs={"pk": self.branch.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["branch"], self.branch)

    def test_branch_delete_success(self) -> None:
        """The branch delete view uses the shared JSON delete behaviour."""
        grant_permissions(self.user, "delete_branch")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.equipment:branch_delete", kwargs={"pk": self.branch.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_machine_list_renders(self) -> None:
        """Users with the view permission can list machines."""
        grant_permissions(self.user, "view_machine")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.equipment:machine_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.machine, response.context["machines"])

    def test_branch_list_renders(self) -> None:
        """Users with the view permission can list branches."""
        grant_permissions(self.user, "view_branch")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.equipment:branch_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.branch, response.context["branches"])

    def test_branch_create_form_renders(self) -> None:
        """Users with the add permission can open the branch form."""
        grant_permissions(self.user, "add_branch")
        self.client.force_login(self.user)
        response = self.client.get(reverse("apps.equipment:branch_create"))
        self.assertEqual(response.status_code, 200)

    def test_branch_update_form_renders(self) -> None:
        """Users with the change permission can open the branch update form."""
        grant_permissions(self.user, "change_branch")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.equipment:branch_update", kwargs={"pk": self.branch.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["branch"], self.branch)

    def test_machine_update_form_renders(self) -> None:
        """Users with the change permission can open the machine form."""
        grant_permissions(self.user, "change_machine")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("apps.equipment:machine_update", kwargs={"pk": self.machine.pk})
        )
        self.assertEqual(response.status_code, 200)

    def machine_formset_data(self, **overrides: object) -> dict:
        """Build a valid machine form payload including formset management data."""
        prefix = forms.ComponentFormSet().prefix
        data: dict = {
            "branch": "",
            "fleet": "",
            "name": "New Machine",
            "serial_number": "SN-NEW-001",
            "model": "MODEL-X",
            "is_active": True,
            f"{prefix}-TOTAL_FORMS": "0",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        data.update(overrides)
        return data

    def test_machine_create_post_creates_machine(self) -> None:
        """A valid machine post creates the machine and its formset."""
        grant_permissions(self.user, "add_machine")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.equipment:machine_create"),
            self.machine_formset_data(),
        )
        self.assertRedirects(
            response,
            reverse("apps.equipment:machine_list"),
            fetch_redirect_response=False,
        )
        self.assertTrue(
            models.Machine.objects.filter(serial_number="SN-NEW-001").exists()
        )

    def test_machine_update_post_updates_machine(self) -> None:
        """A valid machine post updates the instance and its formset."""
        grant_permissions(self.user, "change_machine")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("apps.equipment:machine_update", kwargs={"pk": self.machine.pk}),
            self.machine_formset_data(name="Updated Machine"),
        )
        self.assertRedirects(
            response,
            reverse("apps.equipment:machine_list"),
            fetch_redirect_response=False,
        )
        self.machine.refresh_from_db()
        self.assertEqual(self.machine.name, "Updated Machine")


class EquipmentQueryOptimizationTests(TestCase):
    """The list views select related objects to avoid N+1 queries."""

    def test_machine_list_selects_related(self) -> None:
        """The machine list prefetches branch and fleet."""
        select_related = views.MachineListView().get_queryset().query.select_related
        self.assertIn("branch", select_related)
        self.assertIn("fleet", select_related)

    def test_branch_list_selects_related(self) -> None:
        """The branch list prefetches its location relations."""
        select_related = views.BranchListView().get_queryset().query.select_related
        for field in ("country", "region", "subregion", "city"):
            with self.subTest(field=field):
                self.assertIn(field, select_related)
