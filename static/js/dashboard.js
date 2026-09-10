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
            chart: Object.assign(baseOptions().chart, { type: "donut", height: 280 }),
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
            chart: Object.assign(baseOptions().chart, { type: "bar", height: 280 }),
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
        charts.iso = new ApexCharts(el, Object.assign(baseOptions(), {
            chart: Object.assign(baseOptions().chart, { type: "bar", height: 280 }),
            series: [{ name: "Muestras", data: data.iso4406.values }],
            colors: data.iso4406.status.map(function (status) {
                return status === "normal" ? COLORS.NORMAL : COLORS.CRITICAL;
            }),
            plotOptions: { bar: { columnWidth: "55%", borderRadius: 4, distributed: true } },
            legend: { show: false },
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
        if (total) total.textContent = data.total + " muestras";
        var range = document.getElementById("dashboard-range");
        if (range && data.range.min) {
            range.textContent = data.range.min + " → " + data.range.max;
        }
    }

    function applyData(data) {
        updateKpis(data.kpis);
        updateSummary(data);
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
                var target = button.getAttribute("data-tab");
                Array.prototype.forEach.call(buttons, function (other) {
                    other.classList.toggle("bg-gray-100", other === button);
                    other.classList.toggle("text-primary", other === button);
                    other.classList.toggle("dark:bg-white/[0.05]", other === button);
                });
                Array.prototype.forEach.call(document.querySelectorAll(".tab-panel"), function (panel) {
                    panel.classList.toggle("hidden", panel.id !== "tab-panel-" + target);
                });
            });
        });
        var first = document.querySelector('.tab-btn[data-tab="resumen"]');
        if (first) first.click();
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
        renderAll(currentData);
    });
})();
