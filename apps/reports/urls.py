"""Reports URLs configuration."""

from django.urls import path

from apps.reports import views

app_name = "apps.reports"

urlpatterns = [
    # Laboratory CRUD URLs
    path(
        "laboratories/",
        views.LaboratoryListView.as_view(),
        name="laboratory_list",
    ),
    path(
        "laboratories/create/",
        views.LaboratoryCreateView.as_view(),
        name="laboratory_create",
    ),
    path(
        "laboratories/<int:pk>/",
        views.LaboratoryDetailView.as_view(),
        name="laboratory_detail",
    ),
    path(
        "laboratories/<int:pk>/update/",
        views.LaboratoryUpdateView.as_view(),
        name="laboratory_update",
    ),
    path(
        "laboratories/<int:pk>/delete/",
        views.LaboratoryDeleteView.as_view(),
        name="laboratory_delete",
    ),
    # Report CRUD URLs
    path("", views.ReportListView.as_view(), name="report_list"),
    path("create/", views.ReportCreateView.as_view(), name="report_create"),
    path("<int:pk>/", views.ReportDetailView.as_view(), name="report_detail"),
    path(
        "<int:pk>/update/",
        views.ReportUpdateView.as_view(),
        name="report_update",
    ),
    path(
        "<int:pk>/delete/",
        views.ReportDeleteView.as_view(),
        name="report_delete",
    ),
    # Report export URLs
    path("export/", views.ReportExportPageView.as_view(), name="report_export"),
    path(
        "export/preview/",
        views.ReportExportPreviewAPIView.as_view(),
        name="report_export_preview",
    ),
    path(
        "export/download/",
        views.ReportExportDownloadView.as_view(),
        name="report_export_download",
    ),
    # Analysis Threshold CRUD URLs
    path(
        "thresholds/",
        views.AnalysisThresholdListView.as_view(),
        name="analysisthreshold_list",
    ),
    path(
        "thresholds/create/",
        views.AnalysisThresholdCreateView.as_view(),
        name="analysisthreshold_create",
    ),
    path(
        "thresholds/<int:pk>/",
        views.AnalysisThresholdDetailView.as_view(),
        name="analysisthreshold_detail",
    ),
    path(
        "thresholds/<int:pk>/update/",
        views.AnalysisThresholdUpdateView.as_view(),
        name="analysisthreshold_update",
    ),
    path(
        "thresholds/<int:pk>/delete/",
        views.AnalysisThresholdDeleteView.as_view(),
        name="analysisthreshold_delete",
    ),
        # Component Analysis
    path(
        "analysis/",
        views.ComponentAnalysisView.as_view(),
        name="component_analysis",
    ),
    path(
        "api/analysis/data/",
        views.ComponentAnalysisDataAPIView.as_view(),
        name="analysis_data_api",
    ),
    path(
        "api/analysis/export-pdf/",
        views.ChartExportPDFView.as_view(),
        name="analysis_export_pdf",
    ),
]
