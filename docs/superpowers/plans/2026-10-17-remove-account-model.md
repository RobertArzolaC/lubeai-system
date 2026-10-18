# Remove the `Account` model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the redundant `apps.users.models.Account` model (and everything that only exists to support it), folding its two useful behaviours into `User` / allauth, so the app has a single user identity and a single users UI.

**Architecture:** `Account` is a `OneToOne(User)` soft-deletable profile whose only non-derived value is the `is_removed` flag (used to pick alert-email recipients) plus two derived helpers (`full_name`, `is_email_verified`). We first move the consumers onto `User`, then remove the Accounts CRUD UI/templates in favour of the already-shipped Users UI, and finally drop the model with one migration (data migration turning `is_removed=True` accounts into `is_active=False` users, then `DeleteModel`).

**Tech Stack:** Django 5, django-allauth (`EmailAddress`), django-filter, factory_boy + Django `TestCase`, TailAdmin templates.

**Spec:** Conversación 2026-10-17 (modelo `Account` redundante; `docs/Pendientes.md`: "Revisar si el modelo cuenta es necesario").

## Global Constraints

- All code/comments/docstrings/identifiers in **English**; user-facing strings via `gettext_lazy as _` / `{% trans %}`.
- Type annotations + PEP 257 docstrings on every function/class/test (AGENTS.md).
- Business logic in services; views only orchestrate; scope querysets through `apps.organizations.scoping`.
- **Deactivation decision (my call):** soft-delete (`Account.is_removed`) is replaced by `User.is_active=False`. Alert recipients therefore filter on `user__is_active=True`. Correct or override before executing.
- Verification command (after each task, and full at the end):
  `docker compose exec -T django coverage run manage.py test --settings=config.settings.testing`
  then `docker compose exec -T django coverage report --fail-under=85`.
- Do NOT rename allauth templates under `templates/account/` (they are django-allauth's, unrelated to the model). `DeactivateAccountView`/`DeactivateAccountForm` in `apps/authentication` operate on `User` by email and are **out of scope** (naming only).
- Minimum coverage 85%.

## Review Focus

Failure modes this removal implies; each gets a test in its owning task.

1. Alert notification recipients must stay "active users that can see the alert" — no users silently dropped or added after switching from `Account` to `User` → Task 2.
2. Users whose `Account` had `is_removed=True` must become `is_active=False` (deactivated), not deleted and not left active → Task 5 (data-migration test).
3. No dangling references to `Account`/`is_account`/`user.account` remain anywhere (python, templates) → Tasks 4–6 + Task 7 grep.
4. Deleting a user's profile must no longer cascade-delete the user (the destructive `post_delete(Account)` signal is gone) → Task 5.
5. Profile/Settings pages still render for every user (no `is_account` guard) → Task 3.
6. The Users UI (create/update/deactivate/roles) keeps working after `UserService.create_user` stops creating an `Account` → Task 5.

---

### Task 1: Move `is_email_verified` onto `User`

**Files:**
- Modify: `apps/users/models.py` (add `User.is_email_verified` cached property)
- Test: `apps/users/tests/test_models.py`

**Interfaces:**
- Produces: `User.is_email_verified -> bool` — `EmailAddress.objects.filter(user=self, verified=True).exists()`.

- [ ] **Step 1: Write the failing test**

```python
def test_is_email_verified_true_when_verified(self) -> None:
    """A verified primary email makes ``is_email_verified`` True."""
    EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True, verified=True)
    self.assertTrue(self.user.is_email_verified)
```

- [ ] **Step 2: Run** `docker compose exec -T django python manage.py test apps.users.tests.test_models -v 2` → FAIL (`AttributeError`).
- [ ] **Step 3: Implement `is_email_verified` on `User`** (reuse the query currently in `Account.is_email_verified`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(users): move is_email_verified onto User"`

---

### Task 2: Alert notifications target `User` (drop `Account`)

**Files:**
- Modify: `apps/alerts/services/notifications.py` (`_send_email`, `_dispatch_email` signature)
- Test: `apps/alerts/tests/` (the notification tests that build recipients)

**Interfaces:**
- Consumes: `User.is_active`, `User.email`, `scoping.user_visible_organization_ids`.
- Produces: `_dispatch_email(alerts: QuerySet, user: User) -> None`.

- [ ] **Step 1: Write/adjust the failing test** — an active user with `alerts.view_alert` in the alert's tenant receives the email; an inactive one does not.

```python
def test_inactive_user_is_not_notified(self) -> None:
    """Deactivated users never receive alert emails."""
    self.user.is_active = False
    self.user.save(update_fields=["is_active"])
    result = AlertNotificationService([self.alert.pk]).send()
    self.assertEqual(len(mail.outbox), 0)
```

- [ ] **Step 2: Run** `docker compose exec -T django python manage.py test apps.alerts -v 2` → the new test FAILs (or the module still imports `Account`).
- [ ] **Step 3: Implement** — replace `user_models.Account.objects.filter(user__is_active=True, is_removed=False, ...)` with `user_models.User.objects.filter(is_active=True, organization_id__in=...).select_related("organization")`; update `_dispatch_email` to take a `User` and use `user.email`.
- [ ] **Step 4: Run** `apps.alerts` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "refactor(alerts): select notification recipients from User"`

---

### Task 3: Profile & Settings stop depending on `Account`

**Files:**
- Modify: `apps/users/forms.py` (remove `AccountSettingsForm`)
- Modify: `apps/users/views.py` (`SettingsView`)
- Modify: `templates/users/settings.html`, `templates/users/profile.html`
- Test: `apps/users/tests/test_views.py`, `apps/users/tests/test_forms.py`

**Interfaces:**
- Consumes: `UserSettingsForm`, `User.is_email_verified` (Task 1).
- Produces: `SettingsView` context with only `user_form` (no `account_form`, no `is_account` branch).

- [ ] **Step 1: Write the failing test** — `GET apps.users:settings` renders 200 and its context has no `account_form`; `POST` still saves first/last name.
- [ ] **Step 2: Run** `docker compose exec -T django python manage.py test apps.users.tests.test_views -v 2` → FAIL.
- [ ] **Step 3: Implement** — drop the `is_account` branches; templates use `user.is_email_verified` and remove `account_form`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "refactor(users): settings and profile without Account"`

---

### Task 4: Remove the Accounts UI and its support code

**Files:**
- Modify: `apps/users/views.py` (delete `AccountListView/Create/Update/Delete`)
- Modify: `apps/users/urls.py`, `apps/users/filtersets.py` (delete `AccountFilter`), `apps/users/mixins.py` (delete `PermissionFormMixin` if now unused), `apps/core/breadcrumbs.py` (drop `"account"`), `templates/includes/aside.html` (drop the Accounts item)
- Delete: `templates/users/account/list.html`, `templates/users/account/form.html`
- Modify: `apps/core/tests/test_mixins_views.py` (retarget the minimal views from `Account` to `ComponentType`)
- Delete/adjust tests: `apps/users/tests/test_filtersets.py`, `test_forms.py`, `test_views.py` (account cases), `apps/core/tests/test_templatetags_breadcrumb.py` (account label case)

**Interfaces:**
- Consumes: new Users UI (`apps.users:user_list` etc.) as the replacement.
- Produces: no `account_*` URL names; `apps.core.breadcrumbs.ENTITY_LABELS` without `"account"`.

- [ ] **Step 1: Write the failing test** — `reverse("apps.users:account_list")` raises `NoReverseMatch`; `GET apps.users:user_list` still 200.
- [ ] **Step 2: Run** `docker compose exec -T django python manage.py test apps.users apps.core -v 2` → FAIL.
- [ ] **Step 3: Implement** the deletions above; point `apps/core/tests/test_mixins_views.py` at `apps.equipment.models.ComponentType` with its own permission codenames.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "refactor(users): drop Accounts UI in favour of Users UI"`

---

### Task 5: Delete the `Account` model, signals, admin and service usage (+ migration)

**Files:**
- Modify: `apps/users/models.py` (remove `Account` and `User.is_account`; stop importing `SoftDeletableModel`)
- Modify: `apps/users/signals.py` (remove `create_user_account`, `remove_account_user`)
- Modify: `apps/users/admin.py` (remove `AccountAdmin`)
- Modify: `apps/users/services.py` (remove `Account.objects.get_or_create` from `UserService.create_user`)
- Modify: `apps/users/factories.py` (remove `AccountFactory`)
- Create: `apps/users/migrations/000X_delete_account.py` (`RunPython` deactivate removed-account users, then `DeleteModel`)
- Modify tests: `apps/users/tests/test_models.py`, `test_user_service.py`, `test_user_views.py`, `test_commands.py`

**Interfaces:**
- Produces: users app with **no** `Account` symbol; `User` is the only identity.

- [ ] **Step 1: Write the failing tests**

```python
class RemoveAccountModelTests(TestCase):
    def test_account_model_is_gone(self) -> None:
        with self.assertRaises(AttributeError):
            users_models.Account  # noqa: B018

    def test_removed_account_deactivates_user(self) -> None:
        """Review Focus #2: a soft-deleted account became an inactive user."""
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
```

(The `RunPython` step: capture the ids of `User`s whose `Account.is_removed=True` **before** `DeleteModel`, then set `is_active=False`.)

- [ ] **Step 2: Run** `docker compose exec -T django python manage.py test apps.users -v 2` → FAIL.
- [ ] **Step 3: Implement** the removals and the migration; drop the `Account` assertions in `test_user_service.py`/`test_user_views.py` and the `test_commands.py` filter.
- [ ] **Step 4: Run** `apps.users` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "refactor(users): delete Account model and its signals"`

---

### Task 6: Hygiene — dead code and references

**Files:**
- Modify/Delete: anything left with no reference (`apps/users/mixins.py` if empty; `Account`-only helpers)

- [ ] **Step 1: Audit** (must return nothing)
  ```bash
  grep -rn "Account\|is_account\|is_removed\|user\.account" apps templates --exclude-dir=migrations --exclude-dir=__pycache__
  ```
  Remaining allowed hits: django-allauth's `templates/account/*`, `ACCOUNT_*` settings, allauth imports, and the `DeactivateAccount*` names in `apps/authentication`.
- [ ] **Step 2: Remove** any leftover dead helper; run `ruff check apps --fix` and `ruff format`.
- [ ] **Step 3: Commit** — `git commit -m "chore(users): remove Account leftovers"`

---

### Task 7: Full suite, coverage and `django-reviewer`

- [ ] **Step 1:** `docker compose exec -T django coverage run manage.py test --settings=config.settings.testing` → all pass.
- [ ] **Step 2:** `docker compose exec -T django coverage report --fail-under=85` → ≥ 85%.
- [ ] **Step 3:** Run the `django-reviewer` skill (fresh subagent) over the whole diff; fix Critical/Important with RED→GREEN tests; re-run the suite.
- [ ] **Step 4: Commit** — `git commit -m "refactor(users): finalize Account removal"`

---

## Self-Review

**Spec coverage:** remove `Account` (T5) → move `is_email_verified` (T1) → alerts recipient rewrite (T2) → profile/settings (T3) → UI + breadcrumb + sidebar + core test model (T4) → dead-code audit (T6) → verification + review (T7). ✅

**Step scan:** each step is one checkable action; tests are named with assertions; no "handle edge cases". ✅

**Type consistency:** `User.is_email_verified` (T1) consumed by templates in T3; `_dispatch_email(..., user)` (T2) consistent; `Account` is removed only in T5 after all consumers (T2–T4) stop using it. ✅

**Review Focus:** each of the six failure modes maps to a named task/test. ✅

**Proportion:** 7 tasks, each a self-contained testable deliverable. ✅

## Out of scope (note for later)

- Renaming `DeactivateAccountView`/`DeactivateAccountForm` (naming only) and `ACCOUNT_*` settings.
- The `alerts` recipient logic could later move behind a `RecipientService`.
