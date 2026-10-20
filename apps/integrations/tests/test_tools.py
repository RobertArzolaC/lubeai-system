"""Tests for the MCP tools' authorization, scoping and filters."""

from __future__ import annotations

from apps.alerts import factories as alert_factories
from apps.equipment import factories as equipment_factories
from apps.integrations.tests.base import IntegrationTenantTestCase
from apps.organizations import factories as organization_factories
from apps.reports import factories as report_factories
from apps.users import factories as user_factories


class ToolTestCase(IntegrationTenantTestCase):
    """Base data for tool tests."""

    def setUp(self) -> None:
        super().setUp()
        self.organization = organization_factories.OrganizationFactory()
        self.user = user_factories.UserFactory(organization=self.organization)
        self.grant_permissions(
            self.user,
            "equipment.view_machine",
            "reports.view_report",
            "alerts.view_alert",
        )
        self.client_record = self.create_oauth_client()
        _access, self.access_token, _refresh, _refresh_value = self.create_tokens(
            user=self.user, client=self.client_record
        )
        self.machine = equipment_factories.MachineFactory(
            organization=self.organization,
            branch__organization=self.organization,
        )
        self.component = equipment_factories.ComponentFactory(
            machine=self.machine,
            type__organization=self.organization,
        )
        self.report = report_factories.ReportFactory(
            machine=self.machine,
            component=self.component,
            organization=self.organization,
        )
        report_factories.LabAnalysisFactory(report=self.report)
        self.alert = alert_factories.AlertFactory(
            machine=self.machine,
            component=self.component,
            report=self.report,
            organization=self.organization,
        )

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """Call one tool and return its JSON-RPC result."""
        response = self.mcp_request(
            self.access_token,
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["result"]

    def token_for_new_user(self, *labels: str) -> str:
        """Create a user with the given permissions and return an access token."""
        user = user_factories.UserFactory(organization=self.organization)
        if labels:
            self.grant_permissions(user, *labels)
        _access, access_token, _refresh, _refresh_value = self.create_tokens(
            user=user, client=self.client_record
        )
        return access_token


class EquipmentToolTests(ToolTestCase):
    """Scoping, filters and permissions for equipment tools."""

    def test_list_equipment_returns_only_own_organization(self) -> None:
        """Another organization's machines never appear."""
        other_org = organization_factories.OrganizationFactory()
        equipment_factories.MachineFactory(
            organization=other_org, branch__organization=other_org
        )
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {"name": "list_equipment", "arguments": {}},
            )
        )
        self.assertEqual(result["total"], 1)

    def test_list_equipment_paginates(self) -> None:
        """Limit and offset are applied."""
        equipment_factories.MachineFactory(
            organization=self.organization,
            branch__organization=self.organization,
            name="Second machine",
        )
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {
                    "name": "list_equipment",
                    "arguments": {"limit": 1, "offset": 1},
                },
            )
        )
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["results"]), 1)

    def test_get_equipment_includes_components_and_last_report(self) -> None:
        """The detail includes components, last report and open alerts."""
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {"name": "get_equipment", "arguments": {"machine_id": self.machine.pk}},
            )
        )
        self.assertEqual(result["machine"]["id"], self.machine.pk)
        self.assertEqual(len(result["machine"]["components"]), 1)
        self.assertEqual(result["last_report"]["id"], self.report.pk)
        self.assertGreaterEqual(result["open_alerts"], 1)

    def test_get_equipment_rejects_other_organization(self) -> None:
        """A machine from another organization is reported in-band."""
        other_org = organization_factories.OrganizationFactory()
        other_machine = equipment_factories.MachineFactory(
            organization=other_org, branch__organization=other_org
        )
        result = self.call_tool("get_equipment", {"machine_id": other_machine.pk})
        self.assertTrue(result["isError"])
        self.assertIn("no encontrado", result["content"][0]["text"])

    def test_equipment_only_user_does_not_receive_last_report(self) -> None:
        """Equipment permission alone must not expose report contents."""
        token = self.token_for_new_user("equipment.view_machine")
        result = self.mcp_tool_result(
            self.mcp_request(
                token,
                "tools/call",
                {"name": "get_equipment", "arguments": {"machine_id": self.machine.pk}},
            )
        )
        self.assertIsNone(result["last_report"])

    def test_equipment_only_user_does_not_receive_open_alert_count(self) -> None:
        """Equipment permission alone must not expose alert counts."""
        token = self.token_for_new_user("equipment.view_machine")
        result = self.mcp_tool_result(
            self.mcp_request(
                token,
                "tools/call",
                {"name": "get_equipment", "arguments": {"machine_id": self.machine.pk}},
            )
        )
        self.assertEqual(result["open_alerts"], 0)

    def test_list_components_filters_by_machine(self) -> None:
        """Components can be limited to one machine."""
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {
                    "name": "list_components",
                    "arguments": {"machine_id": self.machine.pk},
                },
            )
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["results"][0]["machine_name"], self.machine.name)


class ReportToolTests(ToolTestCase):
    """Filters and detail for reports."""

    def test_list_reports_filters_by_condition(self) -> None:
        """The condition filter is applied."""
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {
                    "name": "list_reports",
                    "arguments": {"condition": self.report.condition},
                },
            )
        )
        self.assertEqual(result["total"], 1)

    def test_get_report_includes_analysis_and_alerts(self) -> None:
        """The detail includes the lab analysis and linked alerts."""
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {"name": "get_report", "arguments": {"report_id": self.report.pk}},
            )
        )
        self.assertEqual(result["report"]["id"], self.report.pk)
        self.assertIsNotNone(result["analysis"])
        self.assertIn(self.alert.pk, [alert["id"] for alert in result["alerts"]])

    def test_get_report_rejects_other_organization(self) -> None:
        """A report from another organization is reported in-band."""
        other_org = organization_factories.OrganizationFactory()
        other_machine = equipment_factories.MachineFactory(
            organization=other_org, branch__organization=other_org
        )
        other_report = report_factories.ReportFactory(
            machine=other_machine,
            component=equipment_factories.ComponentFactory(
                machine=other_machine, type__organization=other_org
            ),
            organization=other_org,
        )
        result = self.call_tool("get_report", {"report_id": other_report.pk})
        self.assertTrue(result["isError"])
        self.assertIn("no encontrado", result["content"][0]["text"])

    def test_reports_only_user_does_not_receive_alert_details(self) -> None:
        """Reports permission alone must not expose alert contents."""
        token = self.token_for_new_user("reports.view_report")
        result = self.mcp_tool_result(
            self.mcp_request(
                token,
                "tools/call",
                {"name": "get_report", "arguments": {"report_id": self.report.pk}},
            )
        )
        self.assertEqual(result["alerts"], [])


class AlertToolTests(ToolTestCase):
    """Filters and detail for alerts."""

    def test_list_alerts_filters_by_severity(self) -> None:
        """The severity filter is applied."""
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {
                    "name": "list_alerts",
                    "arguments": {"severity": self.alert.severity},
                },
            )
        )
        self.assertGreaterEqual(result["total"], 1)
        self.assertIn(self.alert.pk, [alert["id"] for alert in result["results"]])

    def test_get_alert_returns_report_number(self) -> None:
        """The alert detail links back to the source report."""
        result = self.mcp_tool_result(
            self.mcp_request(
                self.access_token,
                "tools/call",
                {"name": "get_alert", "arguments": {"alert_id": self.alert.pk}},
            )
        )
        self.assertEqual(result["alert"]["id"], self.alert.pk)
        self.assertEqual(result["alert"]["report_lab_number"], self.report.lab_number)

    def test_user_without_permission_does_not_see_alert_tool(self) -> None:
        """Tools are hidden when the user lacks the Django permission."""
        user = user_factories.UserFactory(organization=self.organization)
        _access, access_token, _refresh, _refresh_value = self.create_tokens(
            user=user, client=self.client_record
        )
        response = self.mcp_request(access_token, "tools/list")
        self.assertEqual(response.status_code, 200)
        names = {tool["name"] for tool in response.json()["result"]["tools"]}
        self.assertNotIn("list_alerts", names)
        self.assertIn("get_account_overview", names)

    def test_user_without_organization_is_rejected(self) -> None:
        """A token whose user has no organization cannot read tenant data."""
        user = user_factories.UserFactory(organization=None)
        _access, access_token, _refresh, _refresh_value = self.create_tokens(
            user=user, client=self.client_record
        )
        response = self.mcp_request(
            access_token,
            "tools/call",
            {"name": "get_account_overview", "arguments": {}},
        )
        result = response.json()["result"]
        self.assertTrue(result["isError"])
        self.assertIn("organización", result["content"][0]["text"])

    def test_account_overview_hides_counts_without_permissions(self) -> None:
        """A user without module permissions sees zeroed counts."""
        token = self.token_for_new_user()
        result = self.mcp_tool_result(
            self.mcp_request(
                token,
                "tools/call",
                {"name": "get_account_overview", "arguments": {}},
            )
        )
        self.assertEqual(result["machine_count"], 0)
        self.assertEqual(result["component_count"], 0)
        self.assertEqual(result["report_count"], 0)
        self.assertEqual(result["open_alert_count"], 0)
        self.assertEqual(result["accessible_modules"], [])

    def test_account_overview_counts_only_permitted_modules(self) -> None:
        """Equipment permission counts equipment but not reports or alerts."""
        token = self.token_for_new_user("equipment.view_machine")
        result = self.mcp_tool_result(
            self.mcp_request(
                token,
                "tools/call",
                {"name": "get_account_overview", "arguments": {}},
            )
        )
        self.assertEqual(result["machine_count"], 1)
        self.assertEqual(result["component_count"], 1)
        self.assertEqual(result["report_count"], 0)
        self.assertEqual(result["open_alert_count"], 0)
        self.assertEqual(result["accessible_modules"], ["equipment"])

    def test_invalid_arguments_are_reported_in_band(self) -> None:
        """A limit above the schema maximum is rejected without a 500."""
        response = self.mcp_request(
            self.access_token,
            "tools/call",
            {
                "name": "list_equipment",
                "arguments": {"limit": 1000},
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertTrue(result["isError"])
        self.assertIn("Invalid arguments", result["content"][0]["text"])

    def test_unknown_tool_is_a_jsonrpc_error(self) -> None:
        """Unknown tool names are not silently ignored."""
        response = self.mcp_request(
            self.access_token,
            "tools/call",
            {"name": "does_not_exist", "arguments": {}},
        )
        self.assertIn("error", response.json())
