(function () {
    "use strict";

    var root = document.getElementById("dashboard-root");
    if (!root) {
        return;
    }

    var dataUrl = root.getAttribute("data-data-url");
    var dataElement = document.getElementById("dashboard-data");
    var currentData = dataElement ? JSON.parse(dataElement.textContent) : {};
    var charts = {};

    var COLORS = { NORMAL: "#12b76a", CAUTION: "#FFA70B", CRITICAL: "#f04438" };
    var CONDITIONS = ["NORMAL", "CAUTION", "CRITICAL"];
    var EMPTY_MESSAGE = "No samples found.";

    function isDark() {
        return document.documentElement.classList.contains("dark");
    }

    function baseOptions() {
        return {
            chart: {
                toolbar: { show: false },
                background: "transparent",
                fontFamily: "Outfit, sans-serif",
                foreColor: isDark() ? "#AEB7C0" : "#64748B"
            },
            theme: { mode: isDark() ? "dark" : "light" },
            dataLabels: { enabled: false },
            grid: { borderColor: isDark() ? "#2E3A47" : "#E2E8F0" }
        };
    }

    function renderConditionChart(data) {
        var el = document.getElementById("chart-condition");
        if (!el) return;
        charts.condition = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, {
                type: "donut",
                height: 280,
                events: {
                    dataPointSelection: function (event, chartContext, config) {
                        var condition = CONDITIONS[config.dataPointIndex];
                        if (condition) filterTable({ condition: condition });
                    }
                }
            }),
            labels: ["Normal", "Precaución", "Alerta"],
            series: [
                data.condition_distribution.NORMAL || 0,
                data.condition_distribution.CAUTION || 0,
                data.condition_distribution.CRITICAL || 0
            ],
            colors: [COLORS.NORMAL, COLORS.CAUTION, COLORS.CRITICAL],
            legend: { position: "bottom" }
        }));
        charts.condition.render();
    }

    function renderSamplesChart(data) {
        var el = document.getElementById("chart-samples");
        if (!el) return;
        charts.samples = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "line", height: 280 }),
            series: [
                { name: "Total", data: data.samples_by_month.total },
                { name: "Alerta", data: data.samples_by_month.alerts },
                { name: "Precaución", data: data.samples_by_month.cautions }
            ],
            colors: ["#465fff", COLORS.CRITICAL, COLORS.CAUTION],
            stroke: { curve: "smooth", width: 2 },
            xaxis: { categories: data.samples_by_month.categories }
        }));
        charts.samples.render();
    }

    function renderFleetChart(data) {
        var el = document.getElementById("chart-fleet");
        if (!el) return;
        charts.fleet = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, {
                type: "bar",
                height: 280,
                events: {
                    dataPointSelection: function (event, chartContext, config) {
                        var fleet = data.alerts_by_fleet.categories[config.dataPointIndex];
                        if (fleet) filterTable({ fleet: fleet });
                    }
                }
            }),
            series: [{ name: "Alertas", data: data.alerts_by_fleet.values }],
            colors: [COLORS.CAUTION],
            plotOptions: { bar: { horizontal: true, borderRadius: 4 } },
            xaxis: { categories: data.alerts_by_fleet.categories }
        }));
        charts.fleet.render();
    }

    function renderAlertsTimeChart(data) {
        var el = document.getElementById("chart-alerts-time");
        if (!el) return;
        charts.alertsTime = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "line", height: 280 }),
            series: [
                { name: "Alertas", data: data.alerts_over_time.alerts },
                { name: "Precauciones", data: data.alerts_over_time.cautions }
            ],
            colors: [COLORS.CRITICAL, COLORS.CAUTION],
            stroke: { curve: "smooth", width: 2 },
            xaxis: { categories: data.alerts_over_time.categories }
        }));
        charts.alertsTime.render();
    }

    function renderIsoChart(data) {
        var el = document.getElementById("chart-iso");
        if (!el) return;
        var withinTarget = data.iso4406.values.map(function (value, index) {
            return data.iso4406.status[index] === "normal" ? value : 0;
        });
        var aboveTarget = data.iso4406.values.map(function (value, index) {
            return data.iso4406.status[index] === "normal" ? 0 : value;
        });
        charts.iso = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, {
                type: "bar",
                height: 280,
                stacked: true,
                events: {
                    dataPointSelection: function () {
                        filterTable({});
                    }
                }
            }),
            series: [
                { name: "Dentro de meta (≤ 22/20/17)", data: withinTarget },
                { name: "Sobre la meta", data: aboveTarget }
            ],
            colors: [COLORS.NORMAL, COLORS.CRITICAL],
            plotOptions: { bar: { columnWidth: "55%", borderRadius: 4 } },
            legend: { show: true, position: "bottom" },
            xaxis: { categories: data.iso4406.categories }
        }));
        charts.iso.render();
    }

    function destroyCharts() {
        Object.keys(charts).forEach(function (key) {
            if (charts[key]) {
                charts[key].destroy();
            }
        });
        charts = {};
    }

    function renderAll(data) {
        currentData = data;
        destroyCharts();
        renderConditionChart(data);
        renderSamplesChart(data);
        renderFleetChart(data);
        renderAlertsTimeChart(data);
        renderIsoChart(data);
    }

    function updateKpis(kpis) {
        var mapping = {
            "kpi-total": kpis.total,
            "kpi-normal": kpis.normal,
            "kpi-caution": kpis.caution,
            "kpi-critical": kpis.critical,
            "kpi-rate": kpis.non_conformance_rate + "%"
        };
        Object.keys(mapping).forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.textContent = mapping[id];
        });
    }

    function updateSummary(data) {
        var total = document.getElementById("dashboard-total");
        if (total) total.textContent = data.total;
        var range = document.getElementById("dashboard-range");
        if (range && data.range.min) {
            range.textContent = data.range.min + " → " + data.range.max;
        }
    }

    function renderTable(reports) {
        var body = document.getElementById("dashboard-table-body");
        if (!body) return;
        reports = reports || [];
        while (body.firstChild) body.removeChild(body.firstChild);
        reports.forEach(function (report) {
            var row = document.createElement("tr");
            row.className = "border-t border-gray-100 dark:border-gray-800";
            row.setAttribute("data-condition", report.condition || "");
            row.setAttribute("data-fleet", report.fleet || "");
            [
                report.lab_number,
                report.machine,
                report.fleet,
                report.component,
                report.sample_date,
                report.condition_display
            ].forEach(function (value) {
                var cell = document.createElement("td");
                cell.className = "px-3 py-2";
                cell.textContent = value == null ? "" : value;
                row.appendChild(cell);
            });
            body.appendChild(row);
        });
        var emptyRow = document.createElement("tr");
        emptyRow.setAttribute("data-empty-state", "true");
        if (reports.length > 0) emptyRow.classList.add("hidden");
        var emptyCell = document.createElement("td");
        emptyCell.className = "px-3 py-6 text-center text-gray-500";
        emptyCell.colSpan = 6;
        emptyCell.textContent = EMPTY_MESSAGE;
        emptyRow.appendChild(emptyCell);
        body.appendChild(emptyRow);
    }

    function showTab(slug) {
        var buttons = document.querySelectorAll(".tab-btn");
        Array.prototype.forEach.call(buttons, function (button) {
            var active = button.id === "tab-btn-" + slug;
            button.classList.toggle("bg-gray-100", active);
            button.classList.toggle("text-primary", active);
            button.classList.toggle("dark:bg-white/[0.05]", active);
        });
        Array.prototype.forEach.call(document.querySelectorAll(".tab-panel"), function (panel) {
            panel.classList.toggle("hidden", panel.id !== "tab-panel-" + slug);
        });
    }

    function filterTable(criteria) {
        var body = document.getElementById("dashboard-table-body");
        if (!body) return;
        criteria = criteria || {};
        var matches = 0;
        Array.prototype.forEach.call(
            body.querySelectorAll("tr[data-condition][data-fleet]"),
            function (row) {
                var conditionOk = !criteria.condition
                    || row.getAttribute("data-condition") === criteria.condition;
                var fleetOk = !criteria.fleet
                    || row.getAttribute("data-fleet") === criteria.fleet;
                var visible = conditionOk && fleetOk;
                row.classList.toggle("hidden", !visible);
                if (visible) matches += 1;
            }
        );
        var emptyRow = body.querySelector("tr[data-empty-state]");
        if (emptyRow) emptyRow.classList.toggle("hidden", matches > 0);
        showTab("datos");
    }

    function applyData(data) {
        updateKpis(data.kpis);
        updateSummary(data);
        renderTable(data.recent_reports);
        renderAll(data);
    }

    function currentFilters() {
        var form = document.getElementById("dashboard-filters");
        var params = new URLSearchParams();
        if (!form) return params;
        Array.prototype.forEach.call(form.elements, function (field) {
            if (field.name && field.value) params.append(field.name, field.value);
        });
        return params;
    }

    function refresh() {
        fetch(dataUrl + "?" + currentFilters().toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
            .then(function (response) { return response.json(); })
            .then(applyData)
            .catch(function () { /* keep previous data on error */ });
    }

    function setupTabs() {
        var buttons = document.querySelectorAll(".tab-btn");
        Array.prototype.forEach.call(buttons, function (button) {
            button.addEventListener("click", function () {
                showTab(button.getAttribute("data-tab"));
            });
        });
        showTab("resumen");
    }

    function setupFilters() {
        var form = document.getElementById("dashboard-filters");
        if (form) {
            Array.prototype.forEach.call(form.elements, function (field) {
                if (field.tagName === "SELECT") field.addEventListener("change", refresh);
            });
        }
        var reset = document.getElementById("dashboard-reset");
        if (reset) {
            reset.addEventListener("click", function () {
                if (form) {
                    Array.prototype.forEach.call(form.elements, function (field) {
                        if (field.tagName === "SELECT") field.value = "";
                    });
                }
                refresh();
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupTabs();
        setupFilters();
        applyData(currentData);
    });
})();
