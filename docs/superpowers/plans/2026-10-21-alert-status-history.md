# Historial de estados de alertas con descripción y adjunto — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** que el modal de cambio de estado de una alerta registre una descripción y un archivo opcional, conservando un historial por alerta y mostrándolo en el detalle.

**Architecture:** se reutiliza el abstracto `apps.core.models.StatusHistory` con un nuevo `AlertStatusHistory` (FK a `Alert` + `FileField`). La lógica vive en `AlertService.change_status()` dentro de una transacción; la vista solo orquesta HTTP. El adjunto se descarga mediante una vista protegida con el mismo alcance multi-tenant, nunca por URL directa de `MEDIA_URL`.

**Tech Stack:** Django 6, django-tenants, SweetAlert2, Tailwind/TailAdmin, unittest, factory_boy.

**Spec:** conversación de planificación del 2026-10-21 (historial, descripción opcional, PDF/imágenes de hasta 10 MB, instrucciones en español).

## Global Constraints

- Código, nombres, docstrings y `msgid` en inglés; UI, plan y documentación en español (AGENTS.md).
- Type hints y docstrings PEP 257 en todo lo nuevo.
- Migraciones en `apps/alerts/migrations/0005_*`; en despliegue se aplican con `migrate_schemas` porque `alerts` es `TENANT_APP`.
- El modal solo aparece con `alerts.change_alert`; la descarga exige `alerts.view_alert`.
- Todo acceso a datos se filtra por organización (`scoping.scope_queryset`).
- Formatos permitidos: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`; máximo 10 MB.
- La descripción es opcional y el adjunto es opcional.
- Sin dependencias nuevas.
- Tests: `uv run python manage.py test apps.alerts --settings=config.settings.testing --noinput`.
- Lint: `uv run ruff check apps/alerts` y `uv run ruff format --check apps/alerts`.

## Review Focus

1. Archivo con extensión válida pero contenido inválido: el validador debe leer la firma binaria y devolver 400.
2. Adjunto de otra organización: 404, nunca descarga directa ni fuga de metadatos.
3. Archivo cercano a 10 MB: límite consistente en cliente y servidor, con mensaje claro.
4. Dos usuarios cambian el estado a la vez: `transaction.atomic` y una entrada de historial por envío; la última escritura gana en `Alert` sin perder historial.
5. Reapertura (`OPEN`): limpia `acknowledged_at/by` y `resolved_at` sin borrar el historial.

---

### Task 1: Validación, modelo `AlertStatusHistory`, migración, admin y factory

**Files:**
- Create: `apps/alerts/validators.py`
- Modify: `apps/alerts/models.py`
- Create: `apps/alerts/migrations/0005_alertstatushistory.py` (generada)
- Modify: `apps/alerts/admin.py`
- Modify: `apps/alerts/factories.py`
- Create: `apps/alerts/tests/test_models.py`

**Interfaces:**
- Consumes: `apps.core.models.StatusHistory` (`status`, `previous_status`, `note`, `created_by`, `updated_by`, `created`, `modified`).
- Produces:
  - `validators.ALLOWED_ATTACHMENT_EXTENSIONS: tuple[str, ...]`
  - `validators.MAX_ALERT_ATTACHMENT_SIZE: int` (10 MB)
  - `validators.ATTACHMENT_ACCEPT: str`
  - `validators.validate_alert_attachment(file: UploadedFile) -> None`
  - `models.alert_attachment_upload_to(instance, filename) -> str`
  - `models.AlertStatusHistory` con `alert`, `attachment`, `status_label`, `previous_status_label`.
  - `factories.AlertStatusHistoryFactory`.

- [x] **Step 1: Write the failing test** en `apps/alerts/tests/test_models.py`

```python
class AlertStatusHistoryModelTests(AlertTenantTestCase):
    def test_history_orders_newest_first(self) -> None: ...
    def test_upload_path_uses_organization_and_uuid(self) -> None: ...
    def test_status_labels_fall_back_to_raw_value(self) -> None: ...
    def test_create_status_change_links_the_alert(self) -> None: ...
    def test_validator_rejects_a_disallowed_extension(self) -> None: ...
    def test_validator_rejects_a_fake_pdf(self) -> None: ...
    def test_validator_accepts_a_real_pdf(self) -> None: ...
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run python manage.py test apps.alerts.tests.test_models --settings=config.settings.testing --noinput`
Expected: `ImportError: cannot import name 'AlertStatusHistory'`.

- [x] **Step 3: Implement** `apps/alerts/validators.py` (extension + size + firma binaria `%PDF-`, PNG, JPEG, WEBP; ignora `FieldFile` ya guardados) y `apps/alerts/models.py` (modelo, upload path, labels).

- [x] **Step 4: Run test to verify it passes.**

- [x] **Step 5: Generate the migration** con `uv run python manage.py makemigrations alerts`.

- [x] **Step 6: Register in admin** (inline de solo lectura en `AlertAdmin` + `AlertStatusHistoryAdmin`) y añadir `AlertStatusHistoryFactory`.

- [x] **Step 7: Run tests and commit**

```bash
uv run python manage.py test apps.alerts --settings=config.settings.testing --noinput
git add apps/alerts
git commit -m "feat(alerts): add alert status history model"
```

### Task 2: Formulario y servicio de cambio de estado

**Files:**
- Modify: `apps/alerts/forms.py`
- Modify: `apps/alerts/services/alert_service.py`
- Modify: `apps/alerts/tests/test_forms.py`
- Modify: `apps/alerts/tests/test_services.py`

**Interfaces:**
- Consumes: `models.AlertStatusHistory`, `validators.validate_alert_attachment`, `AlertService.apply_status_transition`.
- Produces:
  - `forms.AlertStatusForm` con `status`, `note` (opcional, máx. 1000) y `attachment` (opcional, validador).
  - `AlertService.change_status(alert, *, status, user, note="", attachment=None) -> models.AlertStatusHistory`.

- [x] **Step 1: Write the failing tests** en `test_forms.py` y `test_services.py` (opcionalidad, límite 10 MB, extensión inválida, historial con estado previo/nota/autor, campos de lectura intactos).

- [x] **Step 2: Run tests to verify they fail.**

- [x] **Step 3: Implement** los campos del formulario y `change_status()` con `@transaction.atomic`, `update_fields` (`status`, `acknowledged_at`, `acknowledged_by`, `resolved_at`, `updated_by`, `modified`) y creación del historial.

- [x] **Step 4: Run tests to verify they pass.**

- [x] **Step 5: Commit**

```bash
git add apps/alerts
git commit -m "feat(alerts): validate attachments and record status changes"
```

### Task 3: Endpoint de estado y descarga protegida

**Files:**
- Modify: `apps/alerts/views.py`
- Modify: `apps/alerts/urls.py`
- Modify: `apps/alerts/tests/test_views.py`

**Interfaces:**
- Consumes: `forms.AlertStatusForm`, `AlertService.change_status`, `models.AlertStatusHistory`, `scoping.scope_queryset`.
- Produces:
  - `POST alerts/<pk>/status/` (`multipart/form-data`: `status`, `note`, `attachment`).
  - `GET alerts/history/<pk>/attachment/` → `FileResponse` (nombre `alert_attachment_download`).
  - JSON con `status`, `message`, `new_status`, `new_status_display`, `history_id`, `attachment_url`.

- [x] **Step 1: Write the failing tests** en `test_views.py` (nota persistida, adjunto almacenado, adjunto inválido 400, nota > 1000 → 400, descarga con/sin permiso, scoping, sin archivo → 404, `Content-Disposition: attachment`).

- [x] **Step 2: Run tests to verify they fail.**

- [x] **Step 3: Implement** el modal endpoint con `request.POST, request.FILES`, delegación al servicio, y `AlertAttachmentDownloadView` con `get_object_or_404`, `FileResponse(as_attachment=True)` y `Cache-Control: private, no-store`.

- [x] **Step 4: Run tests to verify they pass.**

- [x] **Step 5: Commit**

```bash
git add apps/alerts
git commit -m "feat(alerts): serve status attachments through a scoped view"
```

### Task 4: Modal del listado

**Files:**
- Modify: `templates/alerts/alert/list.html`
- Modify: `apps/alerts/views.py` (contexto `attachment_accept` y `attachment_max_size`)
- Modify: `apps/alerts/tests/test_templates.py`

**Interfaces:**
- Consumes: `status_choices`, `attachment_accept`, `attachment_max_size`.
- Produces: modal SweetAlert2 con `id="alert-status-value"`, `id="alert-status-note"`, `id="alert-status-attachment"` y envío `FormData`.

- [x] **Step 1: Write the failing test** en `test_templates.py` (marcadores del modal y `FormData`).

- [x] **Step 2: Run test to verify it fails.**

- [x] **Step 3: Implement** el modal con select de estado, textarea de descripción, input de archivo con `accept`, ayuda de 10 MB, `preConfirm` con validación de tamaño y `fetch` multipart con CSRF.

- [x] **Step 4: Run test to verify it passes.**

- [x] **Step 5: Commit**

```bash
git add apps/alerts templates/alerts/alert/list.html
git commit -m "feat(alerts): collect note and attachment in the status modal"
```

### Task 5: Historial en el detalle

**Files:**
- Modify: `templates/alerts/alert/detail.html`
- Modify: `apps/alerts/models.py` (`attachment_filename`)
- Modify: `apps/alerts/views.py` (`Prefetch`)
- Modify: `apps/alerts/tests/test_templates.py`
- Modify: `apps/alerts/tests/test_models.py`

**Interfaces:**
- Consumes: `alert.status_history`, `entry.status_label`, `entry.previous_status_label`, `entry.attachment_filename`, `alert_attachment_download`.
- Produces: tarjeta “Status history” con línea de tiempo, nota y enlace de descarga.

- [x] **Step 1: Write the failing tests** (la nota y el enlace se renderizan; el número de consultas no crece con las entradas; `attachment_filename` devuelve solo el nombre).

- [x] **Step 2: Run tests to verify they fail.**

- [x] **Step 3: Implement** `attachment_filename`, el `Prefetch` en `AlertDetailView.get_queryset` y la tarjeta de historial.

- [x] **Step 4: Run tests to verify they pass.**

- [x] **Step 5: Commit**

```bash
git add apps/alerts templates/alerts/alert/detail.html
git commit -m "feat(alerts): show the status history on the alert detail"
```

### Task 6: Traducciones y revisión final

**Files:**
- Modify: `locale/es/LC_MESSAGES/django.po`
- Modify: `locale/es/LC_MESSAGES/django.mo`

- [x] **Step 1:** Extraer mensajes nuevos (`makemessages -l es`) y traducir solo las cadenas de esta funcionalidad.
- [x] **Step 2:** Compilar con `compilemessages`.
- [x] **Step 3:** Ejecutar la suite completa de `apps.alerts` y el lint.
- [x] **Step 4:** Revisión con la skill `django-reviewer` sobre el diff acotado y corrección de hallazgos Critical/Important.
- [x] **Step 5:** Commit final.

```bash
git add locale apps/alerts templates/alerts docs/superpowers/plans
git commit -m "feat(alerts): localize and review the status history flow"
```
