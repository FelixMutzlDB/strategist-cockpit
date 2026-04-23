"""Integration tests for Databricks components.

These tests verify connectivity to external Databricks services.
They are skipped when credentials are not configured (CI-safe).
Mark with: pytest -m integration
"""

import os
import pytest

SKIP_REASON = "Databricks credentials not configured"
HAS_CREDS = bool(os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN"))


@pytest.mark.integration
@pytest.mark.skipif(not HAS_CREDS, reason=SKIP_REASON)
class TestDatabricksSQL:
    """Test connectivity to Databricks SQL Warehouse."""

    def test_warehouse_connection(self):
        from databricks.sql import connect

        host = os.environ["DATABRICKS_HOST"].replace("https://", "")
        token = os.environ["DATABRICKS_TOKEN"]
        warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "071969b1ec9a91ca")

        conn = connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS test_col")
        row = cursor.fetchone()
        assert row[0] == 1
        cursor.close()
        conn.close()

    def test_engagement_details_table_exists(self):
        from databricks.sql import connect

        host = os.environ["DATABRICKS_HOST"].replace("https://", "")
        token = os.environ["DATABRICKS_TOKEN"]
        warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "071969b1ec9a91ca")

        conn = connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM home_felix_mutzl.strategist_canvas.engagement_details")
        count = cursor.fetchone()[0]
        assert count > 0
        cursor.close()
        conn.close()

    def test_unified_view_exists(self):
        from databricks.sql import connect

        host = os.environ["DATABRICKS_HOST"].replace("https://", "")
        token = os.environ["DATABRICKS_TOKEN"]
        warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID", "071969b1ec9a91ca")

        conn = connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token,
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM home_felix_mutzl.strategist_canvas.v_engagements_unified LIMIT 1")
        count = cursor.fetchone()[0]
        assert count >= 0
        cursor.close()
        conn.close()


@pytest.mark.integration
@pytest.mark.skipif(not HAS_CREDS, reason=SKIP_REASON)
class TestServingEndpoint:
    """Test Model Serving endpoint connectivity (Stratego KA)."""

    def test_endpoint_query(self):
        endpoint_name = os.environ.get("STRATEGO_ENDPOINT_NAME")
        if not endpoint_name:
            pytest.skip("STRATEGO_ENDPOINT_NAME not set")

        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient()
        response = w.serving_endpoints.query(
            name=endpoint_name,
            messages=[{"role": "user", "content": "hello"}],
        )
        assert response is not None
        assert response.choices is not None
        assert len(response.choices) > 0
        assert response.choices[0].message.content


@pytest.mark.integration
@pytest.mark.skipif(not HAS_CREDS, reason=SKIP_REASON)
class TestDashboardEmbed:
    """Test that the AI/BI Dashboard is accessible."""

    def test_dashboard_api_access(self):
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient()
        dashboards = w.lakeview.list()
        dashboard_list = list(dashboards)
        strategist_dashboards = [
            d for d in dashboard_list
            if "strategist" in (d.display_name or "").lower()
        ]
        assert len(strategist_dashboards) > 0, "No Strategist dashboard found in workspace"


@pytest.mark.integration
@pytest.mark.skipif(not HAS_CREDS, reason=SKIP_REASON)
class TestGenieSpace:
    """Test Genie Space connectivity."""

    def test_genie_exists(self):
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient()
        genie_spaces = list(w.genie.list())
        strategist_genies = [
            g for g in genie_spaces
            if "strategist" in (getattr(g, "title", "") or "").lower()
            or "cockpit" in (getattr(g, "title", "") or "").lower()
        ]
        assert len(strategist_genies) > 0, "No Strategist Genie Space found"
