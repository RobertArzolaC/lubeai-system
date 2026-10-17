# Client Management (Organizations, Users, Roles) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a laboratory organization manage its child organizations, the users of those organizations, and roles (Django groups + permissions) through new TailAdmin interfaces wired into the sidebar and dashboard.

**Architecture:** The tenancy tree already exists (`apps.organizations.Organization` with `parent`/`children`/`kind`, branding, capabilities). We add full CRUD over the visible subtree, a tenant-scoped `Role` model that wraps a Django `auth.Group`, and a scoped user-management module that creates `User`+`Account`+`EmailAddress` and assigns roles. All views reuse `apps/core/mixins` (`BaseListView`, `BaseCreateView`, `BaseUpdateView`, `BaseDeleteView`, `ClientAttributionMixin`) and `apps/organizations/scoping.py`. Templates extend `layouts/dashboard.html` and reuse the existing `includes/` partials.

**Tech Stack:** Django 5 + Django REST-less CBVs, django-filter, django-allauth, widget-tweaks, Tailwind (TailAdmin), Lucide icons, SweetAlert2 (`showAlert`), factory_boy + Django `TestCase`.

**Spec:** Conversación de diseño (2026-10-17). Decisiones aprobadas: (1) Rol ligado a organización vía `auth.Group`; (2) nueva gestión de Usuarios scoped que convive con Accounts; (3) lista + detalle con pestañas para organizaciones hijas; (4) organizaciones editables con datos + branding + capacidades.

---

## Global Constraints

- All code, comments, docstrings and identifiers in **English**; user-facing strings wrapped in `gettext_lazy as _` / `{% trans %}`.
- **Type annotations + PEP 257 docstrings** on every function, class and test.
- Frontend: **TailAdmin + Tailwind** tokens only (`bg-primary`, `border-stroke`, `text-bodydark2`, `dark:` variants), **Lucide** icons (`data-lucide`), sweetAlert via the existing `showAlert` helper. Do **not** import new fonts or color tokens.
- Use Django `timezone` for any datetime. Use `select_related`/`prefetch_related` to avoid N+1.
- Business logic lives in `services.py`; views only handle HTTP; list scoping via `apps.organizations.scoping`.
- Permissions: reuse Django model permissions — `organizations.{view,add,change,delete}_organization`, `users.{view,add,change,delete}_user`, `users.{view,add,change,delete}_role`.
- Tests are Django `TestCase` with `factory_boy` factories, located in `apps/*/tests/`.
- Verification command (run after each task, and full suite at the end):
  `docker compose exec web coverage run manage.py test --settings=config.settings.testing`
- Minimum coverage 85%.

## Design Direction (frontend-designer)

- **Aesthetic:** industrial-utilitarian, inherited from the existing TailAdmin shell. Consistency over novelty — no new fonts, no new palette.
- **DFII:** Impact 3 + Fit 5 + Feasibility 5 + Performance 5 − Consistency risk 2 = **15/15**.
- **Differentiation anchor (the one memorable element):** a colored **depth spine** on the left edge of each organization row, one segment per ancestor level, plus an inline parent breadcrumb — the hierarchy is readable at a glance without a tree widget. Secondary anchor: the **role → permission matrix** grouped by module with a per-module "select all".
- **Motion:** reuse existing hover transitions only; one entrance fade on the detail tabs.
- **Anti-pattern check:** no purple gradients, no card-grid SaaS template, no system-font headings (inherits Outfit).

## Review Focus

Failure modes the spec implies but no task's happy-path test exercises. Each gets an explicit test in its owning task.

1. Deleting an organization that still has children or users must not silently cascade-destroy a subtree → Task 6.
2. Two roles in the same organization with names that slugify to the same value must be rejected, not crash → Task 2 / Task 3.
3. A tampered form posting an `organization`, `parent` or role outside the actor's subtree must be rejected server-side → Task 5 / Task 9.
4. Setting an organization's `parent` to itself or one of its own descendants (cycle) must be rejected → Task 5.
5. Creating a user whose email already exists must fail with a form error, not an IntegrityError → Task 8.
6. Clearing every permission in the role form must persist an empty permission set (not "leave unchanged") → Task 2.

---

### Task 1: `Role` model, migration, admin, factory

**Files:**
- Modify: `apps/users/models.py` (append `Role`; add `from apps.core import models as core_models` and `from django.contrib.auth.models import Group` — import `Group` lazily via string ref `"auth.Group"` to avoid app-loading issues)
- Create: `apps/users/migrations/000X_role.py` (via `makemigrations`)
- Modify: `apps/users/admin.py` (register `Role` with `autocomplete_fields = ("organization",)`, `filter_horizontal = ("group",)` not needed; show `name`, `organization`, `is_active`)
- Modify: `apps/users/factories.py` (add `RoleFactory`)
- Test: `apps/users/tests/test_models_role.py`

**Interfaces:**
- Produces: `apps.users.models.Role` with fields `organization` (FK → `organizations.Organization`, `related_name="roles"`, `on_delete=CASCADE`), `name: str`, `slug: str`, `description: str`, `group` (OneToOne → `auth.Group`, `related_name="role"`, `on_delete=CASCADE`), plus `TimeStampedModel`/`BaseUserTracked`/`IsActive`. `Meta.constraints = [UniqueConstraint(fields=["organization", "slug"], name="users_role_unique_org_slug")]`, `Meta.ordering = ("name",)`.
- Produces: `apps.users.factories.RoleFactory(organization=SubFactory(OrganizationFactory), name=Sequence, slug=Sequence, group=SubFactory(GroupFactory))`.

- [ ] **Step 1: Write the failing test** — `apps/users/tests/test_models_role.py`

```python
class RoleModelTests(TestCase):
    def test_unique_org_slug_constraint(self) -> None:
        """Two roles in the same organization cannot share a slug."""
        org = organization_factories.OrganizationFactory()
        RoleFactory(organization=org, slug="supervisor")
        with self.assertRaises(IntegrityError):
            RoleFactory(organization=org, slug="supervisor")

    def test_same_slug_allowed_in_different_orgs(self) -> None:
        """The constraint is per organization, not global."""
        a, b = OrganizationFactory(), OrganizationFactory()
        RoleFactory(organization=a, slug="supervisor")
        RoleFactory(organization=b, slug="supervisor")
        self.assertEqual(Role.objects.count(), 2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec web manage.py test apps.users.tests.test_models_role -v 2` → FAIL (no `Role`).

- [ ] **Step 3: Implement `Role` in `apps/users/models.py`, add `RoleFactory`, register in admin, run `makemigrations users`.**

- [ ] **Step 4: Run test to verify it passes** — same command → PASS.

- [ ] **Step 5: Commit** — `git add apps/users && git commit -m "feat(users): add tenant-scoped Role model"`

---

### Task 2: `RoleService` (group + permission sync)

**Files:**
- Create: `apps/users/services.py`
- Modify: `apps/users/signals.py` (add `post_delete` receiver on `Role` deleting its `Group`)
- Test: `apps/users/tests/test_role_service.py`

**Interfaces:**
- Produces: `apps.users.services.RoleService` with:
  - `create_role(self, *, organization, name: str, description: str = "", permissions: Iterable[Permission] = (), actor=None) -> Role`
  - `update_role(self, role: Role, *, name: str, description: str = "", is_active: bool = True, permissions: Iterable[Permission] = (), actor=None) -> Role`
  - `delete_role(self, role: Role) -> None`
  - `@staticmethod build_group_name(organization_id: int, slug: str) -> str` → `f"org{organization_id}:{slug}"`
  - `@staticmethod unique_slug(organization, name: str, *, exclude_pk: int | None = None) -> str`
- Behavior: `create_role` creates `Group(name=build_group_name(...))`, `group.permissions.set(permissions)`, then `Role.objects.create(..., group=group, created_by=actor)`. `update_role` renames the group only if its slug changed, always `group.permissions.set(permissions)` (empty list clears). `delete_role` deletes the group (the role cascades).

- [ ] **Step 1: Write the failing tests**

```python
class RoleServiceTests(TestCase):
    def test_create_sets_permissions_and_group_name(self) -> None:
        org = OrganizationFactory()
        perm = Permission.objects.get(codename="view_report", content_type__app_label="reports")
        role = RoleService().create_role(organization=org, name="Analista", permissions=[perm])
        self.assertEqual(role.group.name, f"org{org.id}:analista")
        self.assertEqual(list(role.group.permissions.all()), [perm])

    def test_update_clears_permissions_when_empty(self) -> None:
        """Review Focus #6: an empty set persists as empty, not "unchanged"."""
        role = RoleFactory()  # group has a permission
        RoleService().update_role(role, name=role.name, permissions=[])
        self.assertEqual(role.group.permissions.count(), 0)

    def test_delete_removes_group(self) -> None:
        role = RoleFactory()
        group_id = role.group_id
        RoleService().delete_role(role)
        self.assertFalse(Group.objects.filter(pk=group_id).exists())

    def test_unique_slug_suffixes_on_collision(self) -> None:
        """Review Focus #2: colliding slugs are suffixed, not crashed."""
        org = OrganizationFactory()
        RoleFactory(organization=org, name="Supervisor", slug="supervisor")
        self.assertEqual(RoleService.unique_slug(org, "Supervisor"), "supervisor-2")
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.users.tests.test_role_service -v 2` → FAIL.
- [ ] **Step 3: Implement `RoleService` + signal.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(users): RoleService syncing Django groups and permissions"`

---

### Task 3: Roles interface (form, list/create/update/delete views, urls, templates)

**Files:**
- Modify: `apps/users/forms.py` (add `RoleForm`)
- Modify: `apps/users/filtersets.py` (add `RoleFilter`)
- Modify: `apps/users/views.py` (add `RoleListView/Create/Update/Delete`)
- Modify: `apps/users/urls.py`
- Create: `templates/users/role/list.html`, `templates/users/role/form.html`, `templates/users/role/_permission_matrix.html`
- Test: `apps/users/tests/test_role_views.py`

**Interfaces:**
- Consumes: `RoleService` (Task 2), `Role`/`RoleFactory` (Task 1).
- Produces: `RoleForm(OrganizationScopeFormMixin, ModelForm)` with `Meta.fields = ["organization", "name", "description", "is_active"]` and an extra `permissions = ModelMultipleChoiceField(queryset=Permission.objects.select_related("content_type").order_by("content_type__app_label", "content_type__model", "codename"), required=False, widget=CheckboxSelectMultiple)`. `__init__(self, *args, user=None, **kwargs)` scopes `organization` via the mixin and sets `self.fields["permissions"].initial = self.instance.group.permissions.all()` when `self.instance.pk`.
- Produces: `RoleFilter` (search `name`, `organization` scoped-filter, `is_active`).
- Produces: views with `permission_required` `users.view_role` / `users.add_role` / `users.change_role` / `users.delete_role`, `tenant_field = "organization"`, templates `users/role/list.html` / `form.html`, success URLs to `apps.users:role_list`.
- Produces routes: `roles/` (`role_list`), `roles/create/` (`role_create`), `roles/<int:pk>/update/` (`role_update`), `roles/<int:pk>/delete/` (`role_delete`).
- View create/update call `RoleService` in `form_valid`; delete overrides `BaseDeleteView.post` to call `RoleService().delete_role(...)`.

- [ ] **Step 1: Write the failing tests**

```python
class RoleViewTests(TestCase):
    def setUp(self) -> None:
        self.user = UserFactory()
        self.client.force_login(self.user)
        grant(self.user, "view_role")

    def test_list_requires_permission(self) -> None:
        RoleViewTests...  # user without perm → 403

    def test_create_persists_role_and_permissions(self) -> None:
        self.user.user_permissions.add(Permission.objects.get(codename="add_role"))
        org = self.user.organization
        response = self.client.post(reverse("apps.users:role_create"), {
            "organization": org.pk, "name": "Analista", "description": "",
            "is_active": "on", "permissions": [perm.pk for perm in self.perms],
        })
        self.assertRedirects(response, reverse("apps.users:role_list"))
        role = Role.objects.get(name="Analista")
        self.assertEqual(role.group.permissions.count(), len(self.perms))

    def test_create_rejects_foreign_organization(self) -> None:
        """Review Focus #3: org outside the actor's subtree is rejected."""
        ...
        self.assertFalse(Role.objects.exists())

    def test_delete_removes_group(self) -> None:
        ...
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.users.tests.test_role_views -v 2` → FAIL.
- [ ] **Step 3: Implement form, filterset, views, urls, templates.** The permission matrix partial renders permissions grouped by `content_type.app_label`/`model`, each group with a header and a `select all` checkbox wired by a small inline script.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(users): role management UI with permission matrix"`

---

### Task 4: `OrganizationService` (slug + subtree guard)

**Files:**
- Modify: `apps/organizations/services.py`
- Test: `apps/organizations/tests/test_organization_service.py`

**Interfaces:**
- Produces: `apps.organizations.services.OrganizationService` with:
  - `@staticmethod ensure_unique_slug(name: str, *, exclude_pk: int | None = None) -> str`
  - `@staticmethod assert_valid_parent(organization, parent) -> None` — raises `ValidationError` if `parent` is `organization` or in `organization.descendants(include_self=True)`.
  - `@staticmethod deactivate(organization) -> None` — sets `is_active=False` on the node and its descendants.
- Keeps the existing `ColorPaletteService` untouched.

- [ ] **Step 1: Write the failing tests**

```python
class OrganizationServiceTests(TestCase):
    def test_slug_is_slugified_and_unique(self) -> None:
        OrganizationFactory(slug="minera-andina")
        self.assertEqual(OrganizationService.ensure_unique_slug("Minera Andina"), "minera-andina-2")

    def test_cycle_parent_rejected(self) -> None:
        """Review Focus #4: cannot parent an org to its own descendant."""
        root = OrganizationFactory()
        child = OrganizationFactory(parent=root)
        with self.assertRaises(ValidationError):
            OrganizationService.assert_valid_parent(root, child)
        with self.assertRaises(ValidationError):
            OrganizationService.assert_valid_parent(root, root)

    def test_deactivate_cascades_to_descendants(self) -> None:
        root = OrganizationFactory()
        child = OrganizationFactory(parent=root)
        OrganizationService.deactivate(root)
        child.refresh_from_db()
        self.assertFalse(child.is_active)
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.organizations.tests.test_organization_service -v 2` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(organizations): OrganizationService slug and subtree guards"`

---

### Task 5: `OrganizationForm` + `OrganizationFilter`

**Files:**
- Create: `apps/organizations/forms.py`
- Create: `apps/organizations/filtersets.py`
- Test: `apps/organizations/tests/test_organization_forms.py`, `apps/organizations/tests/test_organization_filters.py`

**Interfaces:**
- Consumes: `OrganizationService` (Task 4), `scoping`.
- Produces: `OrganizationForm(ModelForm)`:
  - `Meta.model = Organization`, `Meta.fields = ["name", "code", "kind", "parent", "phone", "email", "description", "is_active", "logo", "primary_color", "chart_primary", "chart_success", "chart_warning", "chart_danger", "chart_info", "chart_dark", "capabilities"]`.
  - `__init__(self, *args, user=None, **kwargs)`: sets `self.user`; if `user` is not None, `self.fields["parent"].queryset = scoping.visible_organizations(user)` and, when editing, `.exclude(pk__in=self.instance.descendants(include_self=True))`; `self.fields["parent"].required = False`.
  - `clean_parent(self)`: reject parents not visible to `self.user` (`scoping.is_organization_visible`) and call `OrganizationService.assert_valid_parent`.
  - `clean_kind(self)`: `PLATFORM` only selectable by superusers.
  - `save(self, commit=True)`: sets `instance.slug = OrganizationService.ensure_unique_slug(instance.name, exclude_pk=instance.pk)` when `slug` is empty.
- Produces: `OrganizationFilter(FilterSet)`: `name_search` (name/slug/code), `kind` ChoiceFilter, `parent` ModelChoiceFilter scoped via `scoping.scope_choices`, `is_active`. `Meta.fields = ["name_search", "kind", "parent", "is_active"]`.

- [ ] **Step 1: Write the failing tests**

```python
class OrganizationFormTests(TestCase):
    def test_generates_slug_from_name(self) -> None:
        user = UserFactory()
        form = OrganizationForm({"name": "Nueva Planta", "kind": "final"}, user=user)
        self.assertTrue(form.is_valid(), form.errors)
        org = form.save()
        self.assertEqual(org.slug, "nueva-planta")

    def test_parent_queryset_scoped_to_user_subtree(self) -> None:
        ...
        self.assertNotIn(foreign_org, form.fields["parent"].queryset)

    def test_rejects_foreign_parent(self) -> None:
        """Review Focus #3: a parent outside the subtree is rejected."""
        form = OrganizationForm({"name": "X", "kind": "final", "parent": foreign.pk}, user=user)
        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)

    def test_non_superuser_cannot_pick_platform_kind(self) -> None:
        form = OrganizationForm({"name": "X", "kind": "platform"}, user=UserFactory())
        self.assertFalse(form.is_valid())
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.organizations.tests.test_organization_forms apps.organizations.tests.test_organization_filters -v 2` → FAIL.
- [ ] **Step 3: Implement form + filterset.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(organizations): form and filterset with subtree scoping"`

---

### Task 6: Organizations interface (list/create/update/delete + hierarchy spine)

**Files:**
- Create: `apps/organizations/views.py`
- Create: `apps/organizations/urls.py`
- Modify: `config/urls.py` (add `path("organizations/", include("apps.organizations.urls"))`)
- Create: `templates/organizations/organization/list.html`, `templates/organizations/organization/form.html`
- Test: `apps/organizations/tests/test_organization_views.py`

**Interfaces:**
- Consumes: `OrganizationForm`, `OrganizationFilter` (Task 5), `OrganizationService` (Task 4), `core.mixins`.
- Produces views:
  - `OrganizationListView(BaseListView)`: `model = Organization`, `permission_required = "organizations.view_organization"`, `context_object_name = "organizations"`, `filterset_class = OrganizationFilter`. `get_queryset()` returns `scoping.visible_organizations(user).select_related("parent").annotate(children_count=Count("children"))`.
  - `OrganizationCreateView(BaseCreateView)`, `OrganizationUpdateView(BaseUpdateView)` (override `get_queryset` → `scoping.visible_organizations(user)`, `get_form_kwargs` adds `user=self.request.user`, template `organizations/organization/form.html`), `OrganizationDeleteView(BaseDeleteView)` with `permission_required = "organizations.delete_organization"`.
  - Delete override: if `organization.children.exists()` or `organization.users.exists()`, return `JsonResponse({"status": "error", "message": _("…has child organizations or users")}, status=400)`.
- Produces routes: `organizations/` (`organization_list`), `organizations/create/` (`organization_create`), `organizations/<int:pk>/update/` (`organization_update`), `organizations/<int:pk>/delete/` (`organization_delete`).
- Templates: list shows columns Organización (name + kind badge) / Cliente padre (breadcrumb) / Sub-organizaciones (count) / Estado / Acciones, with a **depth spine**: iterate `organization.ancestors()` length to render N colored left segments. Uses `includes/row_actions.html`, `includes/status_badge.html`, `includes/delete_script.html`.

- [ ] **Step 1: Write the failing tests**

```python
class OrganizationViewTests(TestCase):
    def test_list_only_shows_subtree(self) -> None:
        ...
        self.assertNotContains(response, foreign.name)

    def test_delete_blocked_with_children(self) -> None:
        """Review Focus #1: deleting a parent with children is refused."""
        response = self.client.post(reverse("apps.organizations:organization_delete", args=[parent.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Organization.objects.filter(pk=parent.pk).exists())

    def test_create_assigns_created_by_and_slug(self) -> None:
        ...
    def test_update_rejects_out_of_scope_pk(self) -> None:
        ...
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.organizations.tests.test_organization_views -v 2` → FAIL.
- [ ] **Step 3: Implement views, urls, templates, config include.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(organizations): organization CRUD UI with hierarchy spine"`

---

### Task 7: Organization detail with tabs (children / users / roles)

**Files:**
- Modify: `apps/organizations/views.py` (`OrganizationDetailView`)
- Modify: `apps/organizations/urls.py` (`organizations/<int:pk>/` → `organization_detail`)
- Create: `templates/organizations/organization/detail.html`
- Test: `apps/organizations/tests/test_organization_detail.py`

**Interfaces:**
- Consumes: everything from Task 6; `apps.users.models.Role` (Task 1).
- Produces: `OrganizationDetailView(BaseDetailView)`, `permission_required = "organizations.view_organization"`, `context_object_name = "organization"`, `get_queryset()` → `scoping.visible_organizations(user)`. Context adds:
  - `children` = `object.children.select_related("parent").annotate(children_count=Count("children"))`
  - `organization_users` = `object.users.select_related("organization").prefetch_related("groups__role").order_by("first_name")`
  - `roles` = `object.roles.select_related("group").prefetch_related("group__permissions")`
  - `branding` = `object.get_branding()`, `capabilities` = `object.resolved_capabilities()`
  - `can_manage_children` / `can_manage_users` / `can_manage_roles` booleans from `self.request.user.has_perm(...)`.
- Template: header card with kind badge + parent breadcrumb + branding swatches + capability chips; three tabs (client-side JS toggle, `role="tablist"`) rendering the three tables; each table's "create" button links to the module's create URL with `?organization=<pk>`.

- [ ] **Step 1: Write the failing tests**

```python
class OrganizationDetailTests(TestCase):
    def test_tabs_render_children_users_roles(self) -> None:
        ...
        self.assertContains(response, child.name)
        self.assertContains(response, user.email)
        self.assertContains(response, role.name)

    def test_out_of_scope_org_404s(self) -> None:
        ...
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.organizations.tests.test_organization_detail -v 2` → FAIL.
- [ ] **Step 3: Implement view + template.** Include `includes/row_actions.html` per tab; the users tab reuses `apps.users` URLs.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(organizations): detail page with children, users and roles tabs"`

---

### Task 8: `UserService` (create/update user + account + email + roles)

**Files:**
- Modify: `apps/users/services.py`
- Test: `apps/users/tests/test_user_service.py`

**Interfaces:**
- Consumes: `RoleService`/`Role` (Tasks 1–2), `models.Account`.
- Produces: `apps.users.services.UserService` with:
  - `create_user(self, *, actor, email: str, first_name: str, last_name: str, organization, roles: Iterable[Role] = (), is_active: bool = True) -> User`
  - `update_user(self, user: User, *, first_name: str, last_name: str, organization, roles: Iterable[Role] = (), is_active: bool = True) -> User`
  - `set_roles(self, user: User, roles: Iterable[Role]) -> None`
- Behavior: `create_user` runs in `transaction.atomic`, raises `ValidationError` when the email exists (Review Focus #5), creates the `User` with a random unusable password (`get_random_string(32)`), creates `Account.objects.create(user=user)` and `EmailAddress.objects.get_or_create(user, email, primary=True, verified=False)`, sends confirmation when `constance.config.ENABLE_SEND_EMAIL`, then calls `set_roles`. `set_roles` removes only groups that back a `Role` (via `Group.objects.filter(role__isnull=False)`) and adds the selected roles' groups, preserving unrelated groups.

- [ ] **Step 1: Write the failing tests**

```python
class UserServiceTests(TestCase):
    def test_create_builds_user_account_and_email(self) -> None:
        user = UserService().create_user(actor=self.actor, email="n@x.pe", first_name="N", last_name="X", organization=self.org)
        self.assertTrue(Account.objects.filter(user=user).exists())
        self.assertTrue(EmailAddress.objects.filter(user=user, verified=False).exists())

    def test_duplicate_email_raises(self) -> None:
        """Review Focus #5."""
        UserFactory(email="dup@x.pe")
        with self.assertRaises(ValidationError):
            UserService().create_user(actor=self.actor, email="dup@x.pe", first_name="D", last_name="P", organization=self.org)

    def test_set_roles_preserves_unrelated_groups(self) -> None:
        user = UserFactory()
        other = Group.objects.create(name="legacy")
        user.groups.add(other)
        role = RoleFactory(organization=self.org)
        UserService().set_roles(user, [role])
        self.assertIn(other, user.groups.all())
        self.assertIn(role.group, user.groups.all())
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.users.tests.test_user_service -v 2` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(users): UserService creating users with accounts and roles"`

---

### Task 9: `UserManagementForm` + `UserFilter`

**Files:**
- Modify: `apps/users/forms.py`
- Modify: `apps/users/filtersets.py`
- Test: `apps/users/tests/test_user_forms.py`, `apps/users/tests/test_user_filters.py`

**Interfaces:**
- Consumes: `UserService` (Task 8).
- Produces: `UserManagementForm(OrganizationScopeFormMixin, ModelForm)`:
  - `Meta.model = User`, `Meta.fields = ["organization", "first_name", "last_name", "email", "is_active"]`.
  - `roles = ModelMultipleChoiceField(queryset=Role.objects.none(), required=False, widget=CheckboxSelectMultiple, label=_("Roles"))`.
  - `__init__(self, *args, organization=None, user=None, **kwargs)`: base scoping via mixin; scopes `roles.queryset` to `Role.objects.filter(is_active=True)` intersected with the actor's visible organizations; pre-selects `self.instance.groups.filter(role__isnull=False)`; if `organization` is given (from the detail-page link), sets `self.fields["organization"].initial = organization`.
  - `email` disabled when editing an existing instance.
- Produces: `UserFilter(FilterSet)`: `name_search` (first/last/email), `organization` scoped, `role` ModelChoiceFilter scoped, `is_active`. `Meta.fields = ["name_search", "organization", "role", "is_active"]`.

- [ ] **Step 1: Write the failing tests**

```python
class UserManagementFormTests(TestCase):
    def test_roles_queryset_scoped_to_visible_orgs(self) -> None:
        ...
        self.assertIn(own_role, form.fields["roles"].queryset)
        self.assertNotIn(foreign_role, form.fields["roles"].queryset)

    def test_rejects_foreign_organization(self) -> None:
        """Review Focus #3."""
        form = UserManagementForm({"organization": foreign.pk, "first_name": "A", "last_name": "B", "email": "a@b.pe", "is_active": "on"}, user=self.actor)
        self.assertFalse(form.is_valid())
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.users.tests.test_user_forms apps.users.tests.test_user_filters -v 2` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(users): user management form and filter"`

---

### Task 10: Users interface (list/create/update/delete)

**Files:**
- Modify: `apps/users/views.py`
- Modify: `apps/users/urls.py`
- Create: `templates/users/user/list.html`, `templates/users/user/form.html`
- Test: `apps/users/tests/test_user_views.py`

**Interfaces:**
- Consumes: `UserManagementForm`, `UserFilter` (Task 9), `UserService` (Task 8).
- Produces views:
  - `UserListView(ClientAttributionMixin, BaseListView)`: `model = User`, `permission_required = "users.view_user"`, `context_object_name = "users"`, `filterset_class = UserFilter`, `template_name = "users/user/list.html"`, `get_queryset()` → `super().get_queryset().select_related("organization").prefetch_related("groups__role")`.
  - `UserCreateView(BaseCreateView)` / `UserUpdateView(BaseUpdateView)`: template `users/user/form.html`, `tenant_field = "organization"`, `permission_required` `users.add_user` / `users.change_user`, `get_form_kwargs` adds `user` and `organization=self.request.GET.get("organization")`. `form_valid` delegates to `UserService` (create or update) and does not call `form.save()`.
  - `UserDeleteView(BaseDeleteView)`: `permission_required = "users.delete_user"`. Override to **deactivate** instead of hard-delete when the user has an `Account` (preserves soft-delete semantics) — return the success JSON.
- Produces routes: `users/` (`user_list`), `users/create/` (`user_create`), `users/<int:pk>/update/` (`user_update`), `users/<int:pk>/delete/` (`user_delete`). Existing `accounts/`, `profile/`, `settings/`, `api/` routes unchanged.

- [ ] **Step 1: Write the failing tests**

```python
class UserViewTests(TestCase):
    def test_list_scoped_to_subtree(self) -> None:
        ...
    def test_create_delegates_to_service(self) -> None:
        response = self.client.post(reverse("apps.users:user_create"), {...})
        self.assertRedirects(response, reverse("apps.users:user_list"))
        self.assertTrue(User.objects.filter(email="nuevo@x.pe").exists())
    def test_delete_deactivates_not_destroys(self) -> None:
        ...
        self.user.refresh_from_db(); self.assertFalse(self.user.is_active)
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.users.tests.test_user_views -v 2` → FAIL.
- [ ] **Step 3: Implement views, urls, templates.** The form template renders role checkboxes as chips.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(users): scoped user management UI"`

---

### Task 11: Sidebar + dashboard entries

**Files:**
- Modify: `templates/includes/aside.html`
- Create: `templates/dashboard/includes/administration.html`
- Modify: `templates/dashboard/index.html`
- Modify: `apps/dashboard/views.py` (`DashboardView.get_context_data` adds `show_client_administration: bool`)
- Test: `apps/dashboard/tests/test_administration_links.py`, `apps/organizations/tests/test_templates.py` (extend)

**Interfaces:**
- Consumes: all route names from Tasks 3, 6, 7, 10.
- Produces:
  - Sidebar group **"Clients"** with items: *Organizaciones* (`apps.organizations:organization_list`, `perms.organizations.view_organization`, lucide `building-2`), *Usuarios* (`apps.users:user_list`, `perms.users.view_user`, `users`), *Roles* (`apps.users:role_list`, `perms.users.view_role`, `shield-check`). The existing *Accounts* item moves into the same group.
  - `dashboard/includes/administration.html`: a three-card quick-access row (Organizaciones / Usuarios / Roles) with counts rendered only when `show_client_administration` is true and the corresponding perm is present. Counts come from `DashboardView` context: `client_counts = {"organizations": …, "users": …, "roles": …}` computed with `scoping.visible_organizations(user)` (orgs `count()`, users `filter(organization__in=…).count()`, roles `filter(organization__in=…).count()`).

- [ ] **Step 1: Write the failing tests**

```python
class AdministrationLinksTests(TestCase):
    def test_sidebar_hides_clients_without_permissions(self) -> None:
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertNotContains(response, reverse("apps.organizations:organization_list"))

    def test_sidebar_shows_clients_with_permissions(self) -> None:
        grant(self.user, "view_organization", "view_user", "view_role")
        response = self.client.get(reverse("apps.dashboard:index"))
        self.assertContains(response, reverse("apps.organizations:organization_list"))
        self.assertContains(response, reverse("apps.users:role_list"))

    def test_dashboard_counts_scoped(self) -> None:
        ...
```

- [ ] **Step 2: Run** `docker compose exec web manage.py test apps.dashboard.tests.test_administration_links -v 2` → FAIL.
- [ ] **Step 3: Implement aside, partial, index include and view context.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): client administration entries in sidebar and dashboard"`

---

### Task 12: Remove dead code + full suite + coverage

**Files:**
- Modify/Delete: audit-driven.
- Test: full suite.

**Interfaces:**
- None consumed by later tasks (final task).

- [ ] **Step 1: Audit for dead code.** Run:
  ```bash
  grep -rn "verify_email_api\|VerifyEmailView" apps templates static
  ```
  Confirmed candidates (no template/JS caller — only a self-referential test):
  - `apps/users/api.py::VerifyEmailView`, its route in `apps/users/urls.py`, and `apps/users/tests/test_api.py::VerifyEmailViewTests`. Confirm with the grep above, then remove all three.
  - Remove any import left unused after Tasks 1–11 (`ruff check apps --fix` reports them).
- [ ] **Step 2: Run the full suite**
  `docker compose exec web coverage run manage.py test --settings=config.settings.testing`
  Expected: all tests pass.
- [ ] **Step 3: Coverage report**
  `docker compose exec web coverage report --fail-under=85`
  Expected: ≥ 85%.
- [ ] **Step 4: Commit** — `git commit -m "chore: remove dead code and reach coverage target"`

---

### Task 13: `django-reviewer` pass

**Files:** none (review only; fixes applied in place if the reviewer finds conventions or ORM issues).

- [ ] **Step 1:** Load the `django-reviewer` skill.
- [ ] **Step 2:** Run it against `apps/organizations/{views,forms,filtersets,services}.py`, `apps/users/{models,views,forms,filtersets,services,signals}.py`, the new templates, and `apps/*/tests/*` for the new modules. Focus: N+1 (`select_related`/`prefetch_related` coverage in detail views), `get_queryset` scoping on every new view, permission enforcement, DRY between `UserManagementForm` and `AccountCreationForm`, and docstring/typing completeness.
- [ ] **Step 3:** Apply fixes; re-run Task 12's suite and coverage.
- [ ] **Step 4: Commit** — `git commit -m "refactor: apply django-reviewer feedback"`

---

## Self-Review

**Spec coverage**
- Child organizations → Tasks 4–7. ✅
- Users of organizations → Tasks 8–10. ✅
- Roles & permissions reusing Django groups/permissions → Tasks 1–3. ✅
- Interfaces with the design skill → Tasks 3, 6, 7, 10, 11 (design direction section; TailAdmin tokens + depth spine + permission matrix). ✅
- Dashboard section updated → Task 11. ✅
- Child hierarchy visible at UI level → Task 6 (spine/breadcrumb) + Task 7 (children tab). ✅
- Update logic for functionality → Tasks 2, 4, 8. ✅
- Remove unused code → Task 12. ✅
- Run the given test command → Tasks 12–13. ✅
- `django-reviewer` validation → Task 13. ✅

**Step scan:** each step is a single action with a checkable result; no "handle edge cases" placeholders; code blocks are kept to signatures and tests only. ✅

**Type consistency:** `Role`/`RoleFactory` (Task 1) → `RoleService` (Task 2) → `RoleForm`/`RoleFilter` (Task 3). `OrganizationService` (Task 4) → `OrganizationForm` (Task 5) → views (Tasks 6–7). `UserService` (Task 8) → `UserManagementForm` (Task 9) → views (Task 10). `set_roles`, `ensure_unique_slug`, `assert_valid_parent`, `build_group_name`, `unique_slug` used consistently. ✅

**Review Focus:** each of the six failure modes points at a named task with a test. ✅

**Proportion:** 13 tasks, each a self-contained testable deliverable. ✅

## Follow-ups (out of scope, note for later)

- Decide whether `Accounts` should eventually be folded into the new *Users* module (kept separate per the approved decision).
- Consider an autocomplete widget for the `parent` field once the org tree grows large.
- Consider seeding demo `Role`s in `seed_demo_data.py`.
