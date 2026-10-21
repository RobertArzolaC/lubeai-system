# PDF adjunto en Report — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** agregar un PDF opcional a `Report`, cargarlo desde el admin, descargarlo desde el listado/detalle con permisos y scoping, y rellenar los informes existentes con un PDF dummy mediante un comando idempotente.

**Architecture:** `FileField` con ruta UUID bajo `media/reports/pdfs/<organización>/`, validador de extensión/tamaño/cabecera `%PDF-`, vista de descarga con `FileResponse` que aplica `view_report` y el scoping por organización, widget de admin sin enlaces directos a `MEDIA_URL`, señales de limpieza de archivos y un comando multi-tenant para el backfill.

**Tech Stack:** Django 6, django-tenants, reportlab, Tailwind/TailAdmin, unittest, factory_boy.

**Spec:** conversación de planificación del 2026-10-21.

## Global Constraints

- Código e identificadores en inglés; UI, plan y documentación en español (AGENTS.md).
- Un PDF opcional por informe; se conserva el último.
- Carga inicial solo desde el admin de Django.
- Sin campo de origen interno/proveedor.
- Límite de 20 MB.
- El backfill solo llena informes sin PDF y recorre todos los tenants (con `--schema` opcional).
- Tests con `docker compose exec -T django python manage.py test ... --settings=config.settings.testing --noinput`.
- Lint con `uv run ruff check` y `uv run ruff format --check`.

## Review Focus

1. Descarga cruzada entre organizaciones o sin `view_report`.
2. Enlaces directos a `/media/` en admin, listado o detalle.
3. Archivos huérfanos al reemplazar o eliminar un informe.
4. Archivos que no son PDF reales aunque tengan extensión `.pdf`.
5. Informes existentes sin PDF: el listado y el detalle no deben romperse.

---

### Task 1: Campo, validación y migración

**Files:**
- Modify: `apps/reports/models.py`
- Create: `apps/reports/validators.py`
- Modify: `apps/reports/constants.py`
- Create: `apps/reports/migrations/0005_report_pdf_file.py`
- Test: `apps/reports/tests/test_models.py`

**Interfaces:**
- Produces: `Report.pdf_file: FileField` opcional; `report_pdf_upload_to(instance, filename) -> str`; `validate_report_pdf(file) -> None`; `MAX_REPORT_PDF_SIZE`.

- [x] **Step 1: Write the failing test**

```python
def test_report_has_optional_pdf_file_field(self) -> None:
    field = models.Report._meta.get_field("pdf_file")
    self.assertTrue(field.blank)
    self.assertFalse(field.null)

def test_valid_pdf_is_accepted(self) -> None:
    report = factories.ReportFactory(
        pdf_file=SimpleUploadedFile(
            "report.pdf", b"%PDF-1.4 test", content_type="application/pdf"
        )
    )
    report.full_clean()
    self.assertTrue(report.pdf_file.name.startswith("reports/pdfs/"))
```

- [x] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T django python manage.py test apps.reports.tests.test_models.ReportModelTests --settings=config.settings.testing --noinput`
Expected: FAIL because the field does not exist.

- [x] **Step 3: Implement the field and validator**

- `report_pdf_upload_to`: `reports/pdfs/<organization_id or "unassigned">/<uuid>.pdf`.
- `validate_report_pdf`: skip non-`UploadedFile`; require `.pdf`; enforce `MAX_REPORT_PDF_SIZE`; require `b"%PDF-"` in the first 1024 bytes.
- `Report.pdf_file = models.FileField(..., blank=True, validators=[validate_report_pdf])`.

- [x] **Step 4: Generate the migration**

Run: `docker compose exec -T django python manage.py makemigrations reports --name report_pdf_file --settings=config.settings.testing --skip-checks`
Expected: `AddField` for `pdf_file`.

- [x] **Step 5: Add rejection tests**

Tests for `.txt`, `.pdf` without header, and oversized file (patch `MAX_REPORT_PDF_SIZE`).

- [x] **Step 6: Run and commit**

Run: `docker compose exec -T django python manage.py test apps.reports.tests.test_models.ReportModelTests --settings=config.settings.testing --noinput`
Expected: PASS.

```bash
git add apps/reports && git commit -m "feat(reports): add optional PDF file to Report"
```

---

### Task 2: Admin seguro y limpieza de archivos

**Files:**
- Create: `apps/reports/widgets.py`
- Create: `templates/reports/widgets/report_pdf_input.html`
- Modify: `apps/reports/admin.py`
- Create: `apps/reports/signals.py`
- Modify: `apps/reports/apps.py`
- Test: `apps/reports/tests/test_admin.py`
- Test: `apps/reports/tests/test_signals.py`

**Interfaces:**
- Consumes: `Report.pdf_file` from Task 1.
- Produces: `ReportPDFInput`, `ReportAdminForm`, `pdf_download_link`, file lifecycle signals.

- [x] **Step 1: Write the failing tests**

- Admin form uses `ReportPDFInput`.
- Admin change page contains the `report_pdf_download` URL and not `MEDIA_URL`.
- Replacing the PDF deletes the old file.
- Deleting the report deletes the PDF.

- [x] **Step 2: Implement the safe widget**

`ReportPDFInput(forms.ClearableFileInput)` with a custom template that shows the file name and clear checkbox without linking to `widget.value.url`.

- [x] **Step 3: Implement `ReportAdminForm` and admin fields**

- `widgets = {"pdf_file": ReportPDFInput(attrs={"accept": "application/pdf"})}`.
- Add `"pdf_file"` and `"pdf_download_link"` to the “Información Básica” fieldset.
- Add `pdf_download_link` to `readonly_fields`; link to `apps.reports:report_pdf_download`.

- [x] **Step 4: Implement the cleanup signals**

- `pre_save`: capture `instance._old_pdf_name` when `pk` exists.
- `post_save`: delete the old file if the name changed.
- `post_delete`: delete the current file.
- Register with `ReportsConfig.ready()`.

- [x] **Step 5: Run and commit**

Run: `docker compose exec -T django python manage.py test apps.reports.tests.test_admin apps.reports.tests.test_signals --settings=config.settings.testing --noinput`
Expected: PASS.

```bash
git add apps/reports templates/reports/widgets && git commit -m "feat(reports): manage report PDFs from the admin"
```

---

### Task 3: Vista de descarga con permisos y scoping

**Files:**
- Modify: `apps/reports/views.py`
- Modify: `apps/reports/urls.py`
- Test: `apps/reports/tests/test_views.py`

**Interfaces:**
- Produces: URL `reports/<pk>/pdf/` named `apps.reports:report_pdf_download`; `ReportPDFDownloadView`.

- [x] **Step 1: Write the failing tests**

- Authorized user gets `200`, `application/pdf`, attachment header.
- Report without PDF → `404`.
- User without permission → `403`.
- Report from another organization → `404`.
- Missing file on disk → `404`.

- [x] **Step 2: Implement `ReportPDFDownloadView`**

Use `get_object_or_404` over `scoping.scope_queryset(Report.objects.only("pk", "lab_number", "pdf_file"), request.user)`, `report.pdf_file.open("rb")`, `get_valid_filename(report.lab_number)` and `FileResponse(..., as_attachment=True, content_type="application/pdf")`.

- [x] **Step 3: Add the URL before update/delete routes and run**

Run: `docker compose exec -T django python manage.py test apps.reports.tests.test_views --settings=config.settings.testing --noinput`
Expected: PASS.

```bash
git add apps/reports && git commit -m "feat(reports): add scoped PDF download endpoint"
```

---

### Task 4: Listado, detalle y traducciones

**Files:**
- Modify: `templates/reports/report/list.html`
- Modify: `templates/reports/report/detail.html`
- Modify: `templates/includes/row_actions.html`
- Modify: `locale/es/LC_MESSAGES/django.po`
- Test: `apps/reports/tests/test_templates.py`

**Interfaces:**
- Consumes: `apps.reports:report_pdf_download` from Task 3.

- [x] **Step 1: Write the failing tests**

- List with PDF contains the download URL and the `PDF` badge.
- List without PDF does not contain that report's download URL.
- Detail with PDF contains the “Download PDF” button; without PDF it does not.

- [x] **Step 2: Extend `row_actions.html`**

Optional `download_url` and `download_enabled`; render a `file-down` anchor gated by `view_perm`.

- [x] **Step 3: Update the list**

- Compute `{% url ... as report_pdf_url %}`.
- Pass `download_url=report_pdf_url download_enabled=report.pdf_file`.
- Add a `PDF` badge next to `lab_number`.

- [x] **Step 4: Update the detail**

Add a “Download PDF” button next to Back/Edit when `report.pdf_file` exists.

- [x] **Step 5: Add Spanish translations and compile**

```bash
docker compose exec -T django python manage.py compilemessages
```

- [x] **Step 6: Run and commit**

Run: `docker compose exec -T django python manage.py test apps.reports.tests.test_templates --settings=config.settings.testing --noinput`
Expected: PASS.

```bash
git add templates apps/reports/tests locale && git commit -m "feat(reports): show PDF download in report list and detail"
```

---

### Task 5: Backfill de PDF dummy

**Files:**
- Create: `apps/reports/services/dummy_pdf.py`
- Create: `apps/reports/management/__init__.py`
- Create: `apps/reports/management/commands/__init__.py`
- Create: `apps/reports/management/commands/add_dummy_report_pdfs.py`
- Create: `apps/reports/management/commands/add_dummy_report_pdfs_tenant.py`
- Test: `apps/reports/tests/test_commands.py`
- Test: `apps/reports/tests/test_services.py`

**Interfaces:**
- Consumes: `Report.pdf_file` and the cleanup signals.
- Produces: `build_dummy_report_pdf(lab_number: str) -> bytes`; commands `add_dummy_report_pdfs` and `add_dummy_report_pdfs_tenant`.

- [x] **Step 1: Test the generator**

`build_dummy_report_pdf("INFORME-000001")` starts with `b"%PDF-"` and is longer than 200 bytes.

- [x] **Step 2: Implement the generator**

Use `reportlab.pdfgen.canvas` with A4, title `DOCUMENTO DE EJEMPLO`, the report number and a placeholder note.

- [x] **Step 3: Test the per-schema command**

- Creates PDFs for reports without one.
- Skips reports with a PDF.
- `--overwrite` replaces the file and deletes the old one.
- Re-running is idempotent.
- `--limit` is respected.

- [x] **Step 4: Implement the per-schema command**

Filter `Q(pdf_file="") | Q(pdf_file__isnull=True)` unless `--overwrite`; save `ContentFile(build_dummy_report_pdf(report.lab_number))`.

- [x] **Step 5: Implement the multi-tenant wrapper**

`BaseTenantCommand` with `COMMAND_NAME = "add_dummy_report_pdfs_tenant"`, `--overwrite`/`--limit`, `skip_public=True` by default and option forwarding like `add_default_users`.

- [x] **Step 6: Run, execute and commit**

Run: `docker compose exec -T django python manage.py test apps.reports.tests.test_commands apps.reports.tests.test_services --settings=config.settings.testing --noinput`
Expected: PASS.

Run the backfill:

```bash
docker compose exec -T django python manage.py add_dummy_report_pdfs
```

Expected: one line per tenant with the number of updated reports.

```bash
git add apps/reports && git commit -m "feat(reports): backfill dummy PDFs for existing reports"
```

---

### Task 6: Validación final con django-reviewer

- [x] **Step 1: Checks**

```bash
docker compose exec -T django python manage.py makemigrations reports --check --dry-run --settings=config.settings.testing --skip-checks
uv run ruff check apps/reports
uv run ruff format --check apps/reports
```

- [x] **Step 2: Full suite**

```bash
docker compose exec -T django python manage.py test apps.reports apps.alerts apps.dashboard apps.integrations --settings=config.settings.testing --noinput
```

- [x] **Step 3: Apply django-reviewer to the diff**

Review download scoping, direct media links, file cleanup, real PDF validation and N+1. Fix findings inside the scope and rerun the suite.
