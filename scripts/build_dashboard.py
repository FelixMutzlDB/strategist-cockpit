"""
Build script for the Strategist Impact Dashboard (Lakeview).

Creates or updates the dashboard via the Databricks Lakeview REST API.
Requires: databricks-sdk (pip install databricks-sdk)

Usage:
  export DATABRICKS_HOST=https://adb-2548836972759138.18.azuredatabricks.net
  export DATABRICKS_TOKEN=<your-token>
  python build_dashboard.py                    # update existing
  python build_dashboard.py --create           # create new copy
  python build_dashboard.py --profile logfood  # use CLI profile
"""

import argparse
import json

from databricks.sdk import WorkspaceClient

# -- Constants ----------------------------------------------------------------
DASHBOARD_ID = "01f0f51a424b1cc0bc6f5feba0c33948"
WAREHOUSE_ID = "927ac096f9833442"
DISPLAY_NAME = "Strategist Impact Dashboard (Felix)"
PARENT_PATH  = "/Users/felix.mutzl@databricks.com"


# -- Dashboard definition ----------------------------------------------------
SERIALIZED_DASHBOARD: dict = {
  "datasets": [
    {
      "name": "ds_portfolio",
      "displayName": "portfolio_overview",
      "queryLines": [
        "SELECT\n",
        "  e.strategist_email,\n",
        "  e.account_id,\n",
        "  e.engagement_type,\n",
        "  e.engagement_format,\n",
        "  e.engagement_status,\n",
        "  e.customer,\n",
        "  e.engagement_title,\n",
        "  e.ae,\n",
        "  e.fy,\n",
        "  e.quarter,\n",
        "  e.ASQ_Start_Date,\n",
        "  e.next_steps,\n",
        "  CASE WHEN e.engagement_type = 'Focus' THEN true ELSE false END AS is_focus,\n",
        "  COALESCE(e.total_dbu_dollars, 0) AS total_dbu_dollars,\n",
        "  e.rev_account_name,\n",
        "  e.territory_region,\n",
        "  e.territory_area,\n",
        "  e.territory_segment\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ") e\n"
      ]
    },
    {
      "name": "ds_timeline",
      "displayName": "engagement_timeline",
      "queryLines": [
        "SELECT\n",
        "  fy,\n",
        "  CASE\n",
        "    WHEN engagement_type IN ('Focus', 'One-off') THEN engagement_type\n",
        "    ELSE 'Unclassified'\n",
        "  END AS eng_type,\n",
        "  COUNT(*) AS engagement_count,\n",
        "  COUNT(DISTINCT account_id) AS account_count,\n",
        "  ROUND(SUM(COALESCE(total_dbu_dollars, 0))) AS total_dbu_dollars\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ")\n",
        "GROUP BY fy, eng_type\n",
        "ORDER BY fy, eng_type\n"
      ]
    },
    {
      "name": "ds_focus_revenue",
      "displayName": "focus_account_revenue",
      "queryLines": [
        "SELECT\n",
        "  e.customer AS account_name,\n",
        "  c.usage_date_string,\n",
        "  c.fiscal_year,\n",
        "  c.usage_date_fiscal_quarter_start,\n",
        "  c.usage_date,\n",
        "  ROUND(SUM(c.dbu_dollars)) AS dbu_dollars,\n",
        "  ROUND(AVG(c.growth_rate), 4) AS growth_rate,\n",
        "  ROUND(SUM(c.dbu_dollars_serverless)) AS dbu_dollars_serverless,\n",
        "  ROUND(SUM(c.dbu_dollars_ai)) AS dbu_dollars_ai,\n",
        "  ROUND(SUM(c.dbu_dollars_sql)) AS dbu_dollars_sql,\n",
        "  ROUND(SUM(c.dbu_dollars_uc)) AS dbu_dollars_uc\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ") e\n",
        "LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "  ON e.account_id = c.account_id\n",
        "WHERE e.engagement_type = 'Focus'\n",
        "  AND c.date_grain = 'quarterly'\n",
        "  AND c.fiscal_year BETWEEN 2024 AND 2027\n",
        "  AND c.bu1 = 'Central'\n",
        "GROUP BY e.customer, c.usage_date_string, c.fiscal_year, c.usage_date_fiscal_quarter_start, c.usage_date\n",
        "ORDER BY e.customer, c.usage_date_fiscal_quarter_start\n"
      ]
    },
    {
      "name": "ds_advisor_benchmark",
      "displayName": "advisor_vs_region_benchmark",
      "queryLines": [
        "SELECT * FROM (\n",
        "  SELECT\n",
        "    'Focus' AS portfolio_type,\n",
        "    fiscal_year,\n",
        "    ROUND(SUM(dbu_dollars)) AS advisor_total_dbu_dollars,\n",
        "    try_divide(\n",
        "      (SUM(dbu_dollars) - LAG(SUM(dbu_dollars)) OVER (ORDER BY fiscal_year)),\n",
        "      LAG(SUM(dbu_dollars)) OVER (ORDER BY fiscal_year)\n",
        "    ) AS advisor_yoy_growth\n",
        "  FROM (\n",
        "    SELECT\n",
        "      src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "      NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "      NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "      NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "      COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "    FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "  ) e\n",
        "  LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c ON e.account_id = c.account_id\n",
        "  WHERE e.engagement_type = 'Focus'\n",
        "    AND c.date_grain = 'quarterly' AND c.fiscal_year BETWEEN 2024 AND 2027 AND c.bu1 = 'Central'\n",
        "  GROUP BY fiscal_year\n",
        ") advisor\n",
        "JOIN (\n",
        "  SELECT\n",
        "    fiscal_year AS region_fiscal_year,\n",
        "    ROUND(SUM(dbu_dollars)) AS region_total_dbu_dollars,\n",
        "    try_divide(\n",
        "      (SUM(dbu_dollars) - LAG(SUM(dbu_dollars)) OVER (ORDER BY fiscal_year)),\n",
        "      LAG(SUM(dbu_dollars)) OVER (ORDER BY fiscal_year)\n",
        "    ) AS region_yoy_growth\n",
        "  FROM main.gtm_gold.rpt_c360_overview_unpivoted\n",
        "  WHERE date_grain = 'quarterly' AND fiscal_year BETWEEN 2024 AND 2027 AND bu1 = 'Central'\n",
        "  GROUP BY fiscal_year\n",
        ") region ON advisor.fiscal_year = region.region_fiscal_year\n"
      ]
    },
    {
      "name": "ds_accounts_yoy",
      "displayName": "accounts_yoy_growth",
      "queryLines": [
        "SELECT\n",
        "  e.customer AS account_name,\n",
        "  e.engagement_type,\n",
        "  e.engagement_format,\n",
        "  c.fiscal_year,\n",
        "  ROUND(SUM(c.dbu_dollars)) AS dbu_dollars,\n",
        "  try_divide(\n",
        "    (SUM(c.dbu_dollars) - LAG(SUM(c.dbu_dollars)) OVER (PARTITION BY e.customer ORDER BY c.fiscal_year)),\n",
        "    LAG(SUM(c.dbu_dollars)) OVER (PARTITION BY e.customer ORDER BY c.fiscal_year)\n",
        "  ) AS yoy_growth\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ") e\n",
        "LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c ON e.account_id = c.account_id\n",
        "WHERE c.date_grain = 'quarterly' AND c.fiscal_year BETWEEN 2024 AND 2027 AND c.bu1 = 'Central'\n",
        "GROUP BY e.customer, e.engagement_type, e.engagement_format, c.fiscal_year\n",
        "ORDER BY e.customer, c.fiscal_year\n"
      ]
    },
    {
      "name": "ds_oneoff",
      "displayName": "oneoff_engagements",
      "queryLines": [
        "SELECT\n",
        "  e.customer,\n",
        "  e.engagement_format,\n",
        "  e.engagement_title,\n",
        "  e.ae,\n",
        "  e.fy,\n",
        "  e.quarter,\n",
        "  e.engagement_status,\n",
        "  e.territory_area,\n",
        "  COALESCE(e.total_dbu_dollars, 0) AS total_dbu_dollars,\n",
        "  e.next_steps\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ") e\n",
        "WHERE e.engagement_type = 'One-off'\n",
        "ORDER BY e.ASQ_Start_Date DESC\n"
      ]
    },
    {
      "name": "ds_impact_kpis",
      "displayName": "impact_kpis",
      "queryLines": [
        "SELECT\n",
        "  COUNT(DISTINCT e.account_id) AS total_accounts,\n",
        "  COUNT(DISTINCT CASE WHEN e.engagement_type = 'Focus' THEN e.account_id END) AS focus_accounts,\n",
        "  COUNT(DISTINCT CASE WHEN e.engagement_type = 'One-off' THEN e.account_id END) AS oneoff_accounts,\n",
        "  COUNT(*) AS total_engagements,\n",
        "  SUM(CASE WHEN e.engagement_type = 'Focus' THEN 1 ELSE 0 END) AS focus_engagements,\n",
        "  SUM(CASE WHEN e.engagement_type = 'One-off' THEN 1 ELSE 0 END) AS oneoff_engagements,\n",
        "  COUNT(DISTINCT e.territory_area) AS territories_covered,\n",
        "  COUNT(DISTINCT e.ae) AS ae_partners\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ") e\n"
      ]
    },
    {
      "name": "ds_engagement_format_mix",
      "displayName": "engagement_format_mix",
      "queryLines": [
        "SELECT\n",
        "  CASE\n",
        "    WHEN engagement_type IN ('Focus', 'One-off') THEN engagement_type\n",
        "    ELSE 'Unclassified'\n",
        "  END AS eng_type,\n",
        "  CASE\n",
        "    WHEN engagement_format IN ('Advisory', 'Keynote Customer Event', 'Point of View') THEN engagement_format\n",
        "    WHEN engagement_format = 'tbc' THEN 'Unclassified'\n",
        "    ELSE engagement_format\n",
        "  END AS eng_format,\n",
        "  COUNT(*) AS cnt,\n",
        "  ROUND(SUM(COALESCE(total_dbu_dollars, 0))) AS total_dbu_dollars\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ")\n",
        "GROUP BY eng_type, eng_format\n",
        "ORDER BY eng_type, cnt DESC\n"
      ]
    },
    {
      "name": "ds_territory",
      "displayName": "territory_coverage",
      "queryLines": [
        "SELECT\n",
        "  territory_area,\n",
        "  CASE\n",
        "    WHEN engagement_type IN ('Focus', 'One-off') THEN engagement_type\n",
        "    ELSE 'Unclassified'\n",
        "  END AS eng_type,\n",
        "  COUNT(*) AS engagement_count,\n",
        "  COUNT(DISTINCT account_id) AS account_count,\n",
        "  ROUND(SUM(COALESCE(total_dbu_dollars, 0))) AS total_dbu_dollars\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ")\n",
        "WHERE territory_area IS NOT NULL\n",
        "GROUP BY territory_area, eng_type\n",
        "ORDER BY total_dbu_dollars DESC\n"
      ]
    },
    {
      "name": "ds_focus_detail",
      "displayName": "focus_account_detail",
      "queryLines": [
        "SELECT\n",
        "  e.customer,\n",
        "  e.engagement_title,\n",
        "  e.ae,\n",
        "  e.fy,\n",
        "  e.engagement_status,\n",
        "  e.territory_area,\n",
        "  COALESCE(e.total_dbu_dollars, 0) AS total_dbu_dollars,\n",
        "  e.next_steps\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ") e\n",
        "WHERE e.engagement_type = 'Focus'\n",
        "ORDER BY e.ASQ_Start_Date DESC\n"
      ]
    },
    {
      "name": "ds_all_acct_revenue",
      "displayName": "all_account_quarterly_revenue",
      "queryLines": [
        "SELECT\n",
        "  e.customer AS account_name,\n",
        "  CASE WHEN e.engagement_type IN ('Focus', 'One-off') THEN e.engagement_type ELSE 'Unclassified' END AS eng_type,\n",
        "  c.usage_date_string,\n",
        "  c.fiscal_year,\n",
        "  c.usage_date_fiscal_quarter_start,\n",
        "  ROUND(SUM(c.dbu_dollars)) AS dbu_dollars\n",
        "FROM (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        ") e\n",
        "LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "  ON e.account_id = c.account_id\n",
        "WHERE c.date_grain = 'quarterly'\n",
        "  AND c.fiscal_year BETWEEN 2024 AND 2027\n",
        "  AND c.bu1 = 'Central'\n",
        "GROUP BY e.customer, eng_type, c.usage_date_string, c.fiscal_year, c.usage_date_fiscal_quarter_start\n",
        "ORDER BY e.customer, c.usage_date_fiscal_quarter_start\n"
      ]
    },
    {
      "name": "ds_oneoff_impact_summary",
      "displayName": "oneoff_impact_summary",
      "queryLines": [
        "WITH eng AS (\n",
        "  SELECT\n",
        "    src.account_id, src.customer, src.strategist_email,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "  WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "eng_dated AS (\n",
        "  SELECT *,\n",
        "    CASE WHEN REGEXP_LIKE(quarter, '^FY[0-9]{2}Q[1-4]$') THEN\n",
        "      make_date(CAST('20' || SUBSTRING(quarter, 3, 2) AS INT) - 1,\n",
        "        CASE SUBSTRING(quarter, 6, 1) WHEN '1' THEN 2 WHEN '2' THEN 5 WHEN '3' THEN 8 WHEN '4' THEN 11 END, 1)\n",
        "    END AS engagement_quarter_start\n",
        "  FROM eng WHERE engagement_type = 'One-off' AND quarter IS NOT NULL\n",
        "),\n",
        "eng_offsets AS (\n",
        "  SELECT e.*, o.qtr_offset, add_months(e.engagement_quarter_start, 3 * o.qtr_offset) AS target_quarter\n",
        "  FROM eng_dated e\n",
        "  CROSS JOIN (SELECT 0 AS qtr_offset UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4) o\n",
        "  WHERE e.engagement_quarter_start IS NOT NULL\n",
        "),\n",
        "account_dbu AS (\n",
        "  SELECT eo.strategist_email, eo.account_id, eo.engagement_quarter_start, eo.qtr_offset, eo.target_quarter,\n",
        "    SUM(c.dbu_dollars) AS account_dbu\n",
        "  FROM eng_offsets eo\n",
        "  LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id = eo.account_id AND c.date_grain = 'quarterly'\n",
        "   AND c.usage_date_fiscal_quarter_start = eo.target_quarter AND c.bu1 = 'Central'\n",
        "  GROUP BY 1,2,3,4,5\n",
        "),\n",
        "region_dbu AS (\n",
        "  SELECT c.usage_date_fiscal_quarter_start AS target_quarter, AVG(quarterly_dbu) AS region_avg_dbu\n",
        "  FROM (\n",
        "    SELECT account_id, usage_date_fiscal_quarter_start, SUM(dbu_dollars) AS quarterly_dbu\n",
        "    FROM main.gtm_gold.rpt_c360_overview_unpivoted WHERE date_grain='quarterly' AND bu1='Central'\n",
        "    GROUP BY 1,2\n",
        "  ) c GROUP BY 1\n",
        "),\n",
        "joined AS (\n",
        "  SELECT ad.strategist_email, ad.account_id, ad.engagement_quarter_start, ad.qtr_offset,\n",
        "    try_divide(ad.account_dbu - FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS account_growth,\n",
        "    try_divide(rd.region_avg_dbu - FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS region_growth\n",
        "  FROM account_dbu ad LEFT JOIN region_dbu rd ON rd.target_quarter = ad.target_quarter\n",
        ")\n",
        "SELECT CAST(qtr_offset AS STRING) AS qtr_offset, 'Advisor portfolio (avg)' AS series, AVG(account_growth) AS avg_growth, COUNT(DISTINCT account_id) AS n_accounts\n",
        "FROM joined WHERE strategist_email IS NOT NULL AND account_growth IS NOT NULL GROUP BY qtr_offset\n",
        "UNION ALL\n",
        "SELECT CAST(qtr_offset AS STRING) AS qtr_offset, 'Central region (avg)' AS series, AVG(region_growth) AS avg_growth, NULL AS n_accounts\n",
        "FROM joined WHERE region_growth IS NOT NULL GROUP BY qtr_offset\n",
        "ORDER BY qtr_offset, series\n"
      ]
    },
    {
      "name": "ds_focus_impact_summary",
      "displayName": "focus_impact_summary",
      "queryLines": [
        "WITH eng AS (\n",
        "  SELECT src.account_id, src.customer, src.strategist_email,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "focus_engagements AS (\n",
        "  SELECT *, CAST('20'||SUBSTRING(fy_clean,3,2) AS INT) AS engagement_fy_int\n",
        "  FROM eng WHERE engagement_type = 'Focus' AND REGEXP_LIKE(fy_clean, '^FY[0-9]{2}$')\n",
        "),\n",
        "current_fy AS (\n",
        "  SELECT CASE WHEN MONTH(current_date()) >= 2 THEN YEAR(current_date()) + 1 ELSE YEAR(current_date()) END AS fy_int\n",
        "),\n",
        "focus_offsets AS (\n",
        "  SELECT f.*, o.fy_offset, f.engagement_fy_int + o.fy_offset AS target_fy\n",
        "  FROM focus_engagements f CROSS JOIN (SELECT 0 AS fy_offset UNION ALL SELECT 1) o\n",
        "  CROSS JOIN current_fy\n",
        "  -- Closed-FY filter: drop rows whose target_fy is the current (in-progress) FY or later.\n",
        "  -- Keeps offset 0 rows always (baseline) so growth from 0 still has an anchor.\n",
        "  WHERE f.engagement_fy_int + o.fy_offset < current_fy.fy_int\n",
        "     OR o.fy_offset = 0\n",
        "),\n",
        "account_fy_dbu AS (\n",
        "  SELECT fo.strategist_email, fo.account_id, fo.customer, fo.engagement_format, fo.engagement_fy_int, fo.fy_offset, fo.target_fy,\n",
        "    SUM(c.dbu_dollars) AS account_dbu\n",
        "  FROM focus_offsets fo LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id=fo.account_id AND c.date_grain='quarterly' AND c.fiscal_year=fo.target_fy AND c.bu1='Central'\n",
        "  GROUP BY 1,2,3,4,5,6,7\n",
        "),\n",
        "region_fy_dbu AS (\n",
        "  SELECT c.fiscal_year AS target_fy, AVG(annual_dbu) AS region_avg_dbu, percentile_approx(annual_dbu, 0.5) AS region_med_dbu\n",
        "  FROM (SELECT account_id, fiscal_year, SUM(dbu_dollars) AS annual_dbu\n",
        "        FROM main.gtm_gold.rpt_c360_overview_unpivoted WHERE date_grain='quarterly' AND bu1='Central' GROUP BY 1,2) c\n",
        "  GROUP BY 1\n",
        "),\n",
        "joined AS (\n",
        "  SELECT ad.strategist_email, ad.account_id, ad.customer, ad.engagement_format, ad.engagement_fy_int, ad.fy_offset,\n",
        "    ad.account_dbu, rd.region_avg_dbu, rd.region_med_dbu,\n",
        "    try_divide(ad.account_dbu - FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset)) AS account_growth,\n",
        "    try_divide(rd.region_avg_dbu - FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset)) AS region_growth_avg,\n",
        "    try_divide(rd.region_med_dbu - FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset)) AS region_growth_med\n",
        "  FROM account_fy_dbu ad LEFT JOIN region_fy_dbu rd ON rd.target_fy = ad.target_fy\n",
        ")\n",
        "SELECT CAST(fy_offset AS STRING) AS fy_offset, 'Advisor portfolio (avg)' AS series, AVG(account_growth) AS avg_growth, COUNT(DISTINCT account_id) AS n_accounts\n",
        "FROM joined WHERE strategist_email IS NOT NULL AND account_growth IS NOT NULL GROUP BY fy_offset\n",
        "UNION ALL\n",
        "SELECT CAST(fy_offset AS STRING), 'Central region (avg)', AVG(region_growth_avg), NULL FROM joined WHERE region_growth_avg IS NOT NULL GROUP BY fy_offset\n",
        "ORDER BY fy_offset, series\n"
      ]
    },
    {
      "name": "ds_oneoff_impact_summary_median",
      "displayName": "oneoff_impact_summary_median",
      "queryLines": [
        "WITH eng AS (\n",
        "  SELECT src.account_id, src.customer, src.strategist_email,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "eng_dated AS (\n",
        "  SELECT *, CASE WHEN REGEXP_LIKE(quarter, '^FY[0-9]{2}Q[1-4]$') THEN\n",
        "    make_date(CAST('20'||SUBSTRING(quarter,3,2) AS INT)-1,\n",
        "      CASE SUBSTRING(quarter,6,1) WHEN '1' THEN 2 WHEN '2' THEN 5 WHEN '3' THEN 8 WHEN '4' THEN 11 END, 1)\n",
        "    END AS engagement_quarter_start\n",
        "  FROM eng WHERE engagement_type = 'One-off' AND quarter IS NOT NULL\n",
        "),\n",
        "eng_offsets AS (\n",
        "  SELECT e.*, o.qtr_offset, add_months(e.engagement_quarter_start, 3*o.qtr_offset) AS target_quarter\n",
        "  FROM eng_dated e CROSS JOIN (SELECT 0 AS qtr_offset UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4) o\n",
        "  WHERE e.engagement_quarter_start IS NOT NULL\n",
        "),\n",
        "account_dbu AS (\n",
        "  SELECT eo.strategist_email, eo.account_id, eo.customer, eo.engagement_format, eo.engagement_quarter_start, eo.qtr_offset, eo.target_quarter,\n",
        "    SUM(c.dbu_dollars) AS account_dbu\n",
        "  FROM eng_offsets eo LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id=eo.account_id AND c.date_grain='quarterly' AND c.usage_date_fiscal_quarter_start=eo.target_quarter AND c.bu1='Central'\n",
        "  GROUP BY 1,2,3,4,5,6,7\n",
        "),\n",
        "region_dbu AS (\n",
        "  SELECT c.usage_date_fiscal_quarter_start AS target_quarter, AVG(quarterly_dbu) AS region_avg_dbu, percentile_approx(quarterly_dbu, 0.5) AS region_med_dbu\n",
        "  FROM (SELECT account_id, usage_date_fiscal_quarter_start, SUM(dbu_dollars) AS quarterly_dbu\n",
        "        FROM main.gtm_gold.rpt_c360_overview_unpivoted WHERE date_grain='quarterly' AND bu1='Central' GROUP BY 1,2) c\n",
        "  GROUP BY 1\n",
        "),\n",
        "joined AS (\n",
        "  SELECT ad.strategist_email, ad.account_id, ad.customer, ad.engagement_format, ad.engagement_quarter_start, ad.qtr_offset,\n",
        "    ad.account_dbu, rd.region_avg_dbu, rd.region_med_dbu,\n",
        "    try_divide(ad.account_dbu - FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS account_growth,\n",
        "    try_divide(rd.region_avg_dbu - FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS region_growth_avg,\n",
        "    try_divide(rd.region_med_dbu - FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS region_growth_med\n",
        "  FROM account_dbu ad LEFT JOIN region_dbu rd ON rd.target_quarter = ad.target_quarter\n",
        ")\n",
        "SELECT CAST(qtr_offset AS STRING) AS qtr_offset, 'Advisor portfolio (median)' AS series, percentile_approx(account_growth, 0.5) AS avg_growth, COUNT(DISTINCT account_id) AS n_accounts\n",
        "FROM joined WHERE strategist_email IS NOT NULL AND account_growth IS NOT NULL GROUP BY qtr_offset\n",
        "UNION ALL\n",
        "SELECT CAST(qtr_offset AS STRING), 'Central region (median)', percentile_approx(region_growth_med, 0.5), NULL FROM joined WHERE region_growth_med IS NOT NULL GROUP BY qtr_offset\n",
        "ORDER BY qtr_offset, series\n"
      ]
    },
    {
      "name": "ds_focus_impact_summary_median",
      "displayName": "focus_impact_summary_median",
      "queryLines": [
        "WITH eng AS (\n",
        "  SELECT src.account_id, src.customer, src.strategist_email,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "focus_engagements AS (\n",
        "  SELECT *, CAST('20'||SUBSTRING(fy_clean,3,2) AS INT) AS engagement_fy_int\n",
        "  FROM eng WHERE engagement_type = 'Focus' AND REGEXP_LIKE(fy_clean, '^FY[0-9]{2}$')\n",
        "),\n",
        "current_fy AS (\n",
        "  SELECT CASE WHEN MONTH(current_date()) >= 2 THEN YEAR(current_date()) + 1 ELSE YEAR(current_date()) END AS fy_int\n",
        "),\n",
        "focus_offsets AS (\n",
        "  SELECT f.*, o.fy_offset, f.engagement_fy_int + o.fy_offset AS target_fy\n",
        "  FROM focus_engagements f CROSS JOIN (SELECT 0 AS fy_offset UNION ALL SELECT 1) o\n",
        "  CROSS JOIN current_fy\n",
        "  -- Closed-FY filter: drop rows whose target_fy is the current (in-progress) FY or later.\n",
        "  -- Keeps offset 0 rows always (baseline) so growth from 0 still has an anchor.\n",
        "  WHERE f.engagement_fy_int + o.fy_offset < current_fy.fy_int\n",
        "     OR o.fy_offset = 0\n",
        "),\n",
        "account_fy_dbu AS (\n",
        "  SELECT fo.strategist_email, fo.account_id, fo.customer, fo.engagement_format, fo.engagement_fy_int, fo.fy_offset, fo.target_fy,\n",
        "    SUM(c.dbu_dollars) AS account_dbu\n",
        "  FROM focus_offsets fo LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id=fo.account_id AND c.date_grain='quarterly' AND c.fiscal_year=fo.target_fy AND c.bu1='Central'\n",
        "  GROUP BY 1,2,3,4,5,6,7\n",
        "),\n",
        "region_fy_dbu AS (\n",
        "  SELECT c.fiscal_year AS target_fy, AVG(annual_dbu) AS region_avg_dbu, percentile_approx(annual_dbu, 0.5) AS region_med_dbu\n",
        "  FROM (SELECT account_id, fiscal_year, SUM(dbu_dollars) AS annual_dbu\n",
        "        FROM main.gtm_gold.rpt_c360_overview_unpivoted WHERE date_grain='quarterly' AND bu1='Central' GROUP BY 1,2) c\n",
        "  GROUP BY 1\n",
        "),\n",
        "joined AS (\n",
        "  SELECT ad.strategist_email, ad.account_id, ad.customer, ad.engagement_format, ad.engagement_fy_int, ad.fy_offset,\n",
        "    ad.account_dbu, rd.region_avg_dbu, rd.region_med_dbu,\n",
        "    try_divide(ad.account_dbu - FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset)) AS account_growth,\n",
        "    try_divide(rd.region_avg_dbu - FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset)) AS region_growth_avg,\n",
        "    try_divide(rd.region_med_dbu - FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset)) AS region_growth_med\n",
        "  FROM account_fy_dbu ad LEFT JOIN region_fy_dbu rd ON rd.target_fy = ad.target_fy\n",
        ")\n",
        "SELECT CAST(fy_offset AS STRING) AS fy_offset, 'Advisor portfolio (median)' AS series, percentile_approx(account_growth, 0.5) AS avg_growth, COUNT(DISTINCT account_id) AS n_accounts\n",
        "FROM joined WHERE strategist_email IS NOT NULL AND account_growth IS NOT NULL GROUP BY fy_offset\n",
        "UNION ALL\n",
        "SELECT CAST(fy_offset AS STRING), 'Central region (median)', percentile_approx(region_growth_med, 0.5), NULL FROM joined WHERE region_growth_med IS NOT NULL GROUP BY fy_offset\n",
        "ORDER BY fy_offset, series\n"
      ]
    },
    {
      "name": "ds_oneoff_impact_detail",
      "displayName": "oneoff_impact_detail",
      "queryLines": [
        "WITH eng AS (\n",
        "  SELECT src.account_id, src.customer, src.strategist_email,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "eng_dated AS (\n",
        "  SELECT *, CASE WHEN REGEXP_LIKE(quarter, '^FY[0-9]{2}Q[1-4]$') THEN\n",
        "    make_date(CAST('20'||SUBSTRING(quarter,3,2) AS INT)-1,\n",
        "      CASE SUBSTRING(quarter,6,1) WHEN '1' THEN 2 WHEN '2' THEN 5 WHEN '3' THEN 8 WHEN '4' THEN 11 END, 1)\n",
        "    END AS engagement_quarter_start\n",
        "  FROM eng WHERE engagement_type = 'One-off' AND quarter IS NOT NULL\n",
        "),\n",
        "eng_offsets AS (\n",
        "  SELECT e.*, o.qtr_offset, add_months(e.engagement_quarter_start, 3*o.qtr_offset) AS target_quarter\n",
        "  FROM eng_dated e CROSS JOIN (SELECT 0 AS qtr_offset UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4) o\n",
        "  WHERE e.engagement_quarter_start IS NOT NULL\n",
        "),\n",
        "account_dbu AS (\n",
        "  SELECT eo.strategist_email, eo.account_id, eo.customer, eo.engagement_format, eo.engagement_quarter_start, eo.qtr_offset, eo.target_quarter,\n",
        "    SUM(c.dbu_dollars) AS account_dbu\n",
        "  FROM eng_offsets eo LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id=eo.account_id AND c.date_grain='quarterly' AND c.usage_date_fiscal_quarter_start=eo.target_quarter AND c.bu1='Central'\n",
        "  GROUP BY 1,2,3,4,5,6,7\n",
        "),\n",
        "region_dbu AS (\n",
        "  SELECT c.usage_date_fiscal_quarter_start AS target_quarter, AVG(quarterly_dbu) AS region_avg_dbu, percentile_approx(quarterly_dbu, 0.5) AS region_med_dbu\n",
        "  FROM (SELECT account_id, usage_date_fiscal_quarter_start, SUM(dbu_dollars) AS quarterly_dbu\n",
        "        FROM main.gtm_gold.rpt_c360_overview_unpivoted WHERE date_grain='quarterly' AND bu1='Central' GROUP BY 1,2) c\n",
        "  GROUP BY 1\n",
        "),\n",
        "joined AS (\n",
        "  SELECT ad.strategist_email, ad.account_id, ad.customer, ad.engagement_format, ad.engagement_quarter_start, ad.qtr_offset,\n",
        "    ad.account_dbu, rd.region_avg_dbu, rd.region_med_dbu,\n",
        "    try_divide(ad.account_dbu - FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS account_growth,\n",
        "    try_divide(rd.region_avg_dbu - FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS region_growth_avg,\n",
        "    try_divide(rd.region_med_dbu - FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset),\n",
        "               FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_quarter_start ORDER BY ad.qtr_offset)) AS region_growth_med\n",
        "  FROM account_dbu ad LEFT JOIN region_dbu rd ON rd.target_quarter = ad.target_quarter\n",
        ")\n",
        "SELECT\n",
        "  customer,\n",
        "  engagement_format,\n",
        "  engagement_quarter_start,\n",
        "  qtr_offset,\n",
        "  ROUND(account_dbu, 0) AS account_dbu,\n",
        "  ROUND(region_avg_dbu, 0) AS region_avg_dbu,\n",
        "  account_growth,\n",
        "  region_growth_avg,\n",
        "  account_growth - region_growth_avg AS delta_vs_region\n",
        "FROM joined\n",
        "WHERE strategist_email IS NOT NULL AND qtr_offset > 0\n",
        "ORDER BY customer, engagement_quarter_start, qtr_offset\n"
      ]
    },
    {
      "name": "ds_focus_impact_detail",
      "displayName": "focus_impact_detail",
      "queryLines": [
        "WITH eng AS (\n",
        "  SELECT src.account_id, src.customer, src.strategist_email,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "focus_engagements AS (\n",
        "  SELECT *, CAST('20'||SUBSTRING(fy_clean,3,2) AS INT) AS engagement_fy_int\n",
        "  FROM eng WHERE engagement_type = 'Focus' AND REGEXP_LIKE(fy_clean, '^FY[0-9]{2}$')\n",
        "),\n",
        "current_fy AS (\n",
        "  SELECT CASE WHEN MONTH(current_date()) >= 2 THEN YEAR(current_date()) + 1 ELSE YEAR(current_date()) END AS fy_int\n",
        "),\n",
        "focus_offsets AS (\n",
        "  SELECT f.*, o.fy_offset, f.engagement_fy_int + o.fy_offset AS target_fy\n",
        "  FROM focus_engagements f CROSS JOIN (SELECT 0 AS fy_offset UNION ALL SELECT 1) o\n",
        "  CROSS JOIN current_fy\n",
        "  -- Closed-FY filter: drop rows whose target_fy is the current (in-progress) FY or later.\n",
        "  -- Keeps offset 0 rows always (baseline) so growth from 0 still has an anchor.\n",
        "  WHERE f.engagement_fy_int + o.fy_offset < current_fy.fy_int\n",
        "     OR o.fy_offset = 0\n",
        "),\n",
        "account_fy_dbu AS (\n",
        "  SELECT fo.strategist_email, fo.account_id, fo.customer, fo.engagement_format, fo.engagement_fy_int, fo.fy_offset, fo.target_fy,\n",
        "    SUM(c.dbu_dollars) AS account_dbu\n",
        "  FROM focus_offsets fo LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id=fo.account_id AND c.date_grain='quarterly' AND c.fiscal_year=fo.target_fy AND c.bu1='Central'\n",
        "  GROUP BY 1,2,3,4,5,6,7\n",
        "),\n",
        "region_fy_dbu AS (\n",
        "  SELECT c.fiscal_year AS target_fy, AVG(annual_dbu) AS region_avg_dbu, percentile_approx(annual_dbu, 0.5) AS region_med_dbu\n",
        "  FROM (SELECT account_id, fiscal_year, SUM(dbu_dollars) AS annual_dbu\n",
        "        FROM main.gtm_gold.rpt_c360_overview_unpivoted WHERE date_grain='quarterly' AND bu1='Central' GROUP BY 1,2) c\n",
        "  GROUP BY 1\n",
        "),\n",
        "joined AS (\n",
        "  SELECT ad.strategist_email, ad.account_id, ad.customer, ad.engagement_format, ad.engagement_fy_int, ad.fy_offset,\n",
        "    ad.account_dbu, rd.region_avg_dbu, rd.region_med_dbu,\n",
        "    try_divide(ad.account_dbu - FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset)) AS account_growth,\n",
        "    try_divide(rd.region_avg_dbu - FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset)) AS region_growth_avg,\n",
        "    try_divide(rd.region_med_dbu - FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(rd.region_med_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset)) AS region_growth_med\n",
        "  FROM account_fy_dbu ad LEFT JOIN region_fy_dbu rd ON rd.target_fy = ad.target_fy\n",
        ")\n",
        "SELECT\n",
        "  customer,\n",
        "  engagement_format,\n",
        "  engagement_fy_int,\n",
        "  fy_offset,\n",
        "  ROUND(account_dbu, 0) AS account_dbu,\n",
        "  ROUND(region_avg_dbu, 0) AS region_avg_dbu,\n",
        "  account_growth,\n",
        "  region_growth_avg,\n",
        "  account_growth - region_growth_avg AS delta_vs_region\n",
        "FROM joined\n",
        "WHERE strategist_email IS NOT NULL AND fy_offset > 0\n",
        "ORDER BY customer, engagement_fy_int, fy_offset\n"
      ]
    },
    # --- T-219 evangelism reach datasets ---
    # FY x event_type aggregate. `events_planned_next_30d` is pre-aggregated
    # here (rather than at row level) so the KPI tile can SUM across rows that
    # match the active strategist_email / fy filter. NULL views/participants/
    # comments fold to 0 via COALESCE so SUM stays integer (never NaN).
    {
      "name": "ds_evangelism_summary",
      "displayName": "evangelism_summary",
      "queryLines": [
        "SELECT\n",
        "  strategist_email,\n",
        "  fy,\n",
        "  event_type,\n",
        "  SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END) AS events_delivered,\n",
        "  SUM(CASE WHEN status = 'planned' THEN 1 ELSE 0 END) AS events_planned,\n",
        "  SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS events_cancelled,\n",
        "  SUM(\n",
        "    CASE WHEN status = 'planned'\n",
        "              AND event_date IS NOT NULL\n",
        "              AND event_date >= current_date()\n",
        "              AND event_date <= date_add(current_date(), 30)\n",
        "         THEN 1 ELSE 0 END\n",
        "  ) AS events_planned_next_30d,\n",
        "  COALESCE(SUM(CASE WHEN status = 'delivered' THEN COALESCE(views, 0) ELSE 0 END), 0) AS total_views,\n",
        "  COALESCE(SUM(CASE WHEN status = 'delivered' THEN COALESCE(participants, 0) ELSE 0 END), 0) AS total_attendance,\n",
        "  COALESCE(SUM(CASE WHEN status = 'delivered' THEN COALESCE(comments, 0) ELSE 0 END), 0) AS total_comments,\n",
        "  try_divide(\n",
        "    SUM(CASE WHEN status = 'delivered' THEN COALESCE(views, 0) ELSE 0 END),\n",
        "    SUM(CASE WHEN status = 'delivered' THEN 1 ELSE 0 END)\n",
        "  ) AS avg_views_per_event\n",
        "FROM main.field_strategist_cockpit.evangelism_events\n",
        "GROUP BY strategist_email, fy, event_type\n",
        "ORDER BY fy, event_type\n"
      ]
    },
    # Long-form for the stacked bar: one row per (strategist, fy, quarter,
    # event_type, status). Cancelled rows are kept so the stacked bar can
    # optionally show them; the KPI panels filter to delivered via widget
    # encoding rather than excluding here.
    {
      "name": "ds_evangelism_by_quarter",
      "displayName": "evangelism_by_quarter",
      "queryLines": [
        "SELECT\n",
        "  strategist_email,\n",
        "  fy,\n",
        "  quarter,\n",
        "  event_type,\n",
        "  status,\n",
        "  COUNT(*) AS events_count,\n",
        "  COALESCE(SUM(CASE WHEN status = 'delivered' THEN COALESCE(views, 0) ELSE 0 END), 0) AS views_delivered,\n",
        "  COALESCE(SUM(CASE WHEN status = 'delivered' THEN COALESCE(participants, 0) ELSE 0 END), 0) AS attendance_delivered\n",
        "FROM main.field_strategist_cockpit.evangelism_events\n",
        "WHERE quarter IS NOT NULL\n",
        "GROUP BY strategist_email, fy, quarter, event_type, status\n",
        "ORDER BY fy, quarter, event_type, status\n"
      ]
    },
    # Row-level event detail. Used by two panels: (a) top-N by views detail
    # table (widget applies LIMIT 10 on top of the deterministic SQL ORDER
    # BY views DESC, event_date DESC, event_name ASC); (b) leading-indicator
    # tile filtered by `is_planned_next_30d = true`. `attendance` is an alias
    # for the schema column `participants` so the dashboard's user-facing
    # vocabulary stays consistent with the spec.
    {
      "name": "ds_evangelism_top",
      "displayName": "evangelism_top_events",
      "queryLines": [
        "SELECT\n",
        "  strategist_email,\n",
        "  event_name,\n",
        "  event_date,\n",
        "  event_type,\n",
        "  location,\n",
        "  fy,\n",
        "  quarter,\n",
        "  status,\n",
        "  COALESCE(views, 0) AS views,\n",
        "  COALESCE(participants, 0) AS attendance,\n",
        "  COALESCE(comments, 0) AS comments,\n",
        "  CASE\n",
        "    WHEN status = 'planned'\n",
        "         AND event_date IS NOT NULL\n",
        "         AND event_date >= current_date()\n",
        "         AND event_date <= date_add(current_date(), 30)\n",
        "    THEN true ELSE false\n",
        "  END AS is_planned_next_30d\n",
        "FROM main.field_strategist_cockpit.evangelism_events\n",
        "ORDER BY COALESCE(views, 0) DESC, event_date DESC, event_name ASC\n"
      ]
    }
    # --- end T-219 ---
    ,
    # --- T-222 relationship depth datasets ---
    {
      "name": "ds_exec_meetings_summary",
      "displayName": "exec_meetings_summary",
      "queryLines": [
        "SELECT\n",
        "  strategist_email,\n",
        "  CONCAT('FY', LPAD(MOD(CASE WHEN MONTH(meeting_date) >= 2 THEN YEAR(meeting_date) + 1 ELSE YEAR(meeting_date) END, 100), 2, '0')) AS fy,\n",
        "  COUNT(*) AS meetings_total,\n",
        "  SUM(CASE WHEN is_cxo = TRUE THEN 1 ELSE 0 END) AS cxo_meetings,\n",
        "  COUNT(DISTINCT CASE WHEN is_cxo = TRUE THEN CONCAT(COALESCE(account_id, ''), '|', COALESCE(exec_name, '')) END) AS distinct_cxos,\n",
        "  COUNT(DISTINCT account_id) AS distinct_accounts,\n",
        "  COUNT(DISTINCT CASE WHEN is_cxo = TRUE THEN account_id END) AS distinct_accounts_with_cxo,\n",
        "  SUM(CASE WHEN initiative_id IS NOT NULL THEN 1 ELSE 0 END) AS meetings_tied_to_initiative,\n",
        "  ROUND(try_divide(SUM(CASE WHEN is_cxo = TRUE THEN 1 ELSE 0 END), COUNT(*)) * 100, 1) AS cxo_pct\n",
        "FROM main.field_strategist_cockpit.exec_meetings\n",
        "WHERE strategist_email IS NOT NULL AND meeting_date IS NOT NULL\n",
        "GROUP BY strategist_email, fy\n"
      ]
    },
    {
      "name": "ds_exec_meetings_per_account",
      "displayName": "exec_meetings_per_account",
      "queryLines": [
        "-- One row per exec_meeting (carrying account-level aggregates via window functions),\n",
        "-- PLUS one placeholder row per Focus account with no exec_meeting so the heatmap\n",
        "-- renders a visible gap. Filter out placeholders for non-heatmap panels via is_placeholder = false.\n",
        "WITH em AS (\n",
        "  SELECT\n",
        "    strategist_email, customer, account_id, exec_name, exec_title,\n",
        "    COALESCE(is_cxo, FALSE) AS is_cxo,\n",
        "    meeting_date, asq_id, evangelism_id, initiative_id,\n",
        "    CONCAT('FY', LPAD(MOD(CASE WHEN MONTH(meeting_date) >= 2 THEN YEAR(meeting_date) + 1 ELSE YEAR(meeting_date) END, 100), 2, '0')) AS fy,\n",
        "    CONCAT(\n",
        "      'FY', LPAD(MOD(CASE WHEN MONTH(meeting_date) >= 2 THEN YEAR(meeting_date) + 1 ELSE YEAR(meeting_date) END, 100), 2, '0'),\n",
        "      'Q', CAST(((MOD(MONTH(meeting_date) - 2 + 12, 12)) DIV 3) + 1 AS STRING)\n",
        "    ) AS quarter,\n",
        "    DATE_TRUNC('MONTH', meeting_date) AS meeting_month_start\n",
        "  FROM main.field_strategist_cockpit.exec_meetings\n",
        "  WHERE strategist_email IS NOT NULL AND meeting_date IS NOT NULL\n",
        "),\n",
        "focus_accounts AS (\n",
        "  SELECT DISTINCT src.strategist_email, src.customer, src.account_id\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "  WHERE src.strategist_email IS NOT NULL\n",
        "    AND src.account_id IS NOT NULL\n",
        "    AND NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') = 'Focus'\n",
        "),\n",
        "focus_zero AS (\n",
        "  SELECT\n",
        "    fa.strategist_email, fa.customer, fa.account_id,\n",
        "    CAST(NULL AS STRING) AS exec_name,\n",
        "    FALSE AS is_cxo,\n",
        "    CAST(NULL AS DATE) AS meeting_date,\n",
        "    CAST(NULL AS STRING) AS fy,\n",
        "    CAST(NULL AS STRING) AS quarter,\n",
        "    CAST(NULL AS TIMESTAMP) AS meeting_month_start,\n",
        "    CAST(NULL AS BIGINT) AS initiative_id,\n",
        "    CAST(NULL AS BIGINT) AS evangelism_id,\n",
        "    CAST(NULL AS STRING) AS asq_id,\n",
        "    TRUE AS is_focus,\n",
        "    TRUE AS is_placeholder\n",
        "  FROM focus_accounts fa\n",
        "  LEFT ANTI JOIN em ON em.strategist_email = fa.strategist_email AND em.account_id = fa.account_id\n",
        "),\n",
        "meeting_rows AS (\n",
        "  SELECT\n",
        "    em.strategist_email, em.customer, em.account_id, em.exec_name, em.is_cxo,\n",
        "    em.meeting_date, em.fy, em.quarter, em.meeting_month_start,\n",
        "    em.initiative_id, em.evangelism_id, em.asq_id,\n",
        "    CASE WHEN fa.account_id IS NOT NULL THEN TRUE ELSE FALSE END AS is_focus,\n",
        "    FALSE AS is_placeholder\n",
        "  FROM em\n",
        "  LEFT JOIN focus_accounts fa\n",
        "    ON fa.strategist_email = em.strategist_email AND fa.account_id = em.account_id\n",
        "),\n",
        "combined AS (\n",
        "  SELECT * FROM meeting_rows UNION ALL SELECT * FROM focus_zero\n",
        ")\n",
        "SELECT\n",
        "  c.strategist_email,\n",
        "  c.customer,\n",
        "  c.account_id,\n",
        "  c.exec_name,\n",
        "  c.is_cxo,\n",
        "  c.is_focus,\n",
        "  c.is_placeholder,\n",
        "  c.meeting_date,\n",
        "  c.fy,\n",
        "  c.quarter,\n",
        "  c.meeting_month_start,\n",
        "  CASE WHEN c.is_cxo THEN 'CXO' ELSE 'Non-CXO' END AS cxo_label,\n",
        "  c.initiative_id, c.evangelism_id, c.asq_id,\n",
        "  SUM(CASE WHEN c.is_placeholder THEN 0 ELSE 1 END) OVER (PARTITION BY c.strategist_email, c.account_id) AS total_meetings,\n",
        "  SUM(CASE WHEN c.is_placeholder THEN 0 WHEN c.is_cxo THEN 1 ELSE 0 END) OVER (PARTITION BY c.strategist_email, c.account_id) AS cxo_meetings,\n",
        "  MAX(c.meeting_date) OVER (PARTITION BY c.strategist_email, c.account_id) AS last_meeting_date,\n",
        "  SUM(CASE WHEN c.is_placeholder THEN 0 WHEN c.initiative_id IS NOT NULL THEN 1 ELSE 0 END) OVER (PARTITION BY c.strategist_email, c.account_id) AS linked_initiative_count,\n",
        "  SUM(CASE WHEN c.is_placeholder THEN 0 WHEN c.evangelism_id IS NOT NULL THEN 1 ELSE 0 END) OVER (PARTITION BY c.strategist_email, c.account_id) AS linked_evangelism_count\n",
        "FROM combined c\n",
        "ORDER BY c.account_id, c.meeting_date\n"
      ]
    },
    {
      "name": "ds_exec_meetings_gap",
      "displayName": "exec_meetings_gap",
      "queryLines": [
        "-- Accounts with a CXO exec_meeting in the last 180d AND no customer_engagement\n",
        "-- (any ASQ_Start_Date) in the same 180d window. The 'we have the relationship but\n",
        "-- no work in flight' panel — most actionable view for QBR prep.\n",
        "WITH cxo_recent AS (\n",
        "  SELECT\n",
        "    strategist_email, customer, account_id,\n",
        "    MAX(meeting_date) AS last_cxo_meeting_date\n",
        "  FROM main.field_strategist_cockpit.exec_meetings\n",
        "  WHERE strategist_email IS NOT NULL\n",
        "    AND account_id IS NOT NULL\n",
        "    AND is_cxo = TRUE\n",
        "    AND meeting_date >= DATE_SUB(current_date(), 180)\n",
        "  GROUP BY strategist_email, customer, account_id\n",
        "),\n",
        "eng_recent AS (\n",
        "  SELECT DISTINCT src.strategist_email, src.account_id\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "  WHERE src.strategist_email IS NOT NULL\n",
        "    AND src.account_id IS NOT NULL\n",
        "    AND src.ASQ_Start_Date >= DATE_SUB(current_date(), 180)\n",
        ")\n",
        "SELECT\n",
        "  c.strategist_email,\n",
        "  c.customer,\n",
        "  c.account_id,\n",
        "  c.last_cxo_meeting_date,\n",
        "  DATEDIFF(current_date(), c.last_cxo_meeting_date) AS days_since_engagement\n",
        "FROM cxo_recent c\n",
        "LEFT ANTI JOIN eng_recent e\n",
        "  ON e.strategist_email = c.strategist_email AND e.account_id = c.account_id\n",
        "ORDER BY c.last_cxo_meeting_date DESC\n"
      ]
    }
    # --- end T-222 ---
    ,
    # --- T-213 UCO velocity datasets ---
    # Both datasets read from main.field_strategist_cockpit.v_customer_engagement_uco_velocity
    # (DDL in scripts/init_uc_tables.sql). One row per (engagement_id, uco_id);
    # manual orphans excluded by the view (no asq_uco linkage).
    {
      "name": "ds_uco_velocity_summary",
      "displayName": "uco_velocity_summary",
      "queryLines": [
        "SELECT\n",
        "  current_stage AS stage,\n",
        "  percentile_approx(days_in_current_stage, 0.5) AS median_days_in_stage,\n",
        "  COUNT(DISTINCT engagement_id) AS engagement_count,\n",
        "  COUNT(DISTINCT uco_id) AS uco_count\n",
        "FROM main.field_strategist_cockpit.v_customer_engagement_uco_velocity\n",
        "WHERE strategist_email IS NOT NULL\n",
        "  AND current_stage IN ('U1','U2','U3','U4','U5','U6')\n",
        "GROUP BY current_stage\n",
        "ORDER BY current_stage\n"
      ]
    },
    {
      "name": "ds_uco_velocity_detail",
      "displayName": "uco_velocity_detail",
      "queryLines": [
        # Per-row detail powering the KPI tile (% engagements with ≥1 90d advance),
        # the transitions-per-quarter chart (using most-recent transition only —
        # previous_stage→current_stage at most_recent_stage_change_date), and
        # the detail table. transition_quarter is derived from
        # most_recent_stage_change_date using FY runs Feb→Jan (FY27 = Feb 2026 –
        # Jan 2027), mirroring the convention used elsewhere in this dashboard.
        "SELECT\n",
        "  strategist_email,\n",
        "  engagement_id,\n",
        "  uco_id,\n",
        "  customer,\n",
        "  account_id,\n",
        "  fy,\n",
        "  quarter,\n",
        "  engagement_type,\n",
        "  engagement_format,\n",
        "  ASQ_Start_Date,\n",
        "  current_stage,\n",
        "  previous_stage,\n",
        "  start_stage,\n",
        "  days_in_current_stage,\n",
        "  most_recent_stage_change_date,\n",
        "  stages_advanced_since_engagement_start,\n",
        "  stage_advance_within_90d,\n",
        "  CASE\n",
        "    WHEN previous_stage IN ('U3','U4','U5')\n",
        "     AND current_stage  IN ('U4','U5','U6')\n",
        "     AND CAST(SUBSTRING(current_stage,2,1) AS INT)\n",
        "       = CAST(SUBSTRING(previous_stage,2,1) AS INT) + 1\n",
        "    THEN CONCAT(previous_stage, '->', current_stage)\n",
        "    ELSE NULL\n",
        "  END AS late_stage_transition,\n",
        "  CASE WHEN most_recent_stage_change_date IS NOT NULL THEN\n",
        "    CONCAT(\n",
        "      'FY',\n",
        "      LPAD(CAST(CASE\n",
        "        WHEN MONTH(most_recent_stage_change_date) >= 2\n",
        "        THEN YEAR(most_recent_stage_change_date) + 1 - 2000\n",
        "        ELSE YEAR(most_recent_stage_change_date) - 2000\n",
        "      END AS STRING), 2, '0'),\n",
        "      'Q',\n",
        "      CAST(CEIL(\n",
        "        (CASE WHEN MONTH(most_recent_stage_change_date) >= 2\n",
        "              THEN MONTH(most_recent_stage_change_date) - 1\n",
        "              ELSE MONTH(most_recent_stage_change_date) + 11\n",
        "         END) / 3.0\n",
        "      ) AS INT)\n",
        "    )\n",
        "  END AS transition_quarter\n",
        "FROM main.field_strategist_cockpit.v_customer_engagement_uco_velocity\n",
        "WHERE strategist_email IS NOT NULL\n"
      ]
    }
    # --- end T-213 ---
    ,
    # --- T-212 outcome tags ---
    {
      "name": "ds_activity_impact_tags",
      "displayName": "activity_impact_tags",
      "queryLines": [
        "WITH unified AS (\n",
        "  SELECT category, id, strategist_email, fy, quarter, title\n",
        "  FROM main.field_strategist_cockpit.v_engagement_categories_unified\n",
        "  WHERE strategist_email IS NOT NULL\n",
        "),\n",
        "keyed AS (\n",
        "  SELECT\n",
        "    u.category,\n",
        "    u.id AS activity_id,\n",
        "    u.strategist_email,\n",
        "    u.fy,\n",
        "    u.quarter,\n",
        "    u.title,\n",
        "    CASE u.category\n",
        "      WHEN 'customer'   THEN CONCAT('asq:',        u.id)\n",
        "      WHEN 'evangelism' THEN CONCAT('evangelism:', u.id)\n",
        "      WHEN 'initiative' THEN CONCAT('initiative:', u.id)\n",
        "      ELSE CONCAT(u.category, ':', u.id)\n",
        "    END AS activity_key\n",
        "  FROM unified u\n",
        ")\n",
        "SELECT\n",
        "  k.category,\n",
        "  k.activity_id,\n",
        "  k.activity_key,\n",
        "  k.strategist_email,\n",
        "  k.fy,\n",
        "  k.quarter,\n",
        "  k.title,\n",
        "  tag AS impact_tag\n",
        "FROM keyed k\n",
        "INNER JOIN main.field_strategist_cockpit.activity_app_data a\n",
        "  ON a.category = k.category\n",
        " AND a.strategist_email = k.strategist_email\n",
        " AND a.activity_key = k.activity_key\n",
        "LATERAL VIEW EXPLODE(a.impact_tags) t AS tag\n",
        "WHERE tag IS NOT NULL\n"
      ]
    }
    # --- end T-212 ---
  ],
  "pages": [
    {
      "name": "p_exec_summary",
      "displayName": "Executive Summary",
      "layout": [
        {
          "widget": {
            "name": "header_exec",
            "multilineTextboxSpec": {
              "lines": [
                "# Strategist Impact Dashboard\n",
                "\n",
                "Data & AI Strategist portfolio overview — measuring activity and impact across Focus and One-off engagements.\n",
                "Inspired by the [Impact Players](https://thewisemangroup.com/books/impact-players/) framework: measuring **what changed** because of what you did."
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 0,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_total_accounts",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_impact_kpis",
                  "fields": [
                    {
                      "name": "sum(total_accounts)",
                      "expression": "SUM(`total_accounts`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(total_accounts)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Total Accounts",
                "showDescription": True,
                "description": "All accounts in portfolio"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_focus_accounts",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_impact_kpis",
                  "fields": [
                    {
                      "name": "sum(focus_accounts)",
                      "expression": "SUM(`focus_accounts`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(focus_accounts)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Focus Accounts",
                "showDescription": True,
                "description": "Multi-quarter deep engagements"
              }
            }
          },
          "position": {
            "x": 1,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_oneoff_engagements",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_impact_kpis",
                  "fields": [
                    {
                      "name": "sum(oneoff_engagements)",
                      "expression": "SUM(`oneoff_engagements`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(oneoff_engagements)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "One-off Engagements",
                "showDescription": True,
                "description": "Targeted, topic-specific"
              }
            }
          },
          "position": {
            "x": 2,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_territories",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_impact_kpis",
                  "fields": [
                    {
                      "name": "sum(territories_covered)",
                      "expression": "SUM(`territories_covered`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(territories_covered)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Territories",
                "showDescription": True,
                "description": "Areas covered"
              }
            }
          },
          "position": {
            "x": 3,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_ae_partners",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_impact_kpis",
                  "fields": [
                    {
                      "name": "sum(ae_partners)",
                      "expression": "SUM(`ae_partners`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(ae_partners)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "AE Partners",
                "showDescription": True,
                "description": "Account Executives supported"
              }
            }
          },
          "position": {
            "x": 4,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_total_engagements",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_impact_kpis",
                  "fields": [
                    {
                      "name": "sum(total_engagements)",
                      "expression": "SUM(`total_engagements`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(total_engagements)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Total Engagements",
                "showDescription": True,
                "description": "All engagement records"
              }
            }
          },
          "position": {
            "x": 5,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "chart_timeline",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_timeline",
                  "fields": [
                    {
                      "name": "fy",
                      "expression": "`fy`"
                    },
                    {
                      "name": "sum(engagement_count)",
                      "expression": "SUM(`engagement_count`)"
                    },
                    {
                      "name": "eng_type",
                      "expression": "`eng_type`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "fy",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(engagement_count)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  }
                },
                "color": {
                  "fieldName": "eng_type",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Engagements Over Time"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 4,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_format_mix",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_engagement_format_mix",
                  "fields": [
                    {
                      "name": "eng_format",
                      "expression": "`eng_format`"
                    },
                    {
                      "name": "sum(cnt)",
                      "expression": "SUM(`cnt`)"
                    },
                    {
                      "name": "eng_type",
                      "expression": "`eng_type`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "eng_format",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(cnt)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  }
                },
                "color": {
                  "fieldName": "eng_type",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Engagement Format Mix"
              }
            }
          },
          "position": {
            "x": 3,
            "y": 4,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_territory",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_territory",
                  "fields": [
                    {
                      "name": "territory_area",
                      "expression": "`territory_area`"
                    },
                    {
                      "name": "sum(engagement_count)",
                      "expression": "SUM(`engagement_count`)"
                    },
                    {
                      "name": "eng_type",
                      "expression": "`eng_type`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "territory_area",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(engagement_count)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  }
                },
                "color": {
                  "fieldName": "eng_type",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Engagements by Territory"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 9,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_territory_rev",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_territory",
                  "fields": [
                    {
                      "name": "territory_area",
                      "expression": "`territory_area`"
                    },
                    {
                      "name": "sum(total_dbu_dollars)",
                      "expression": "SUM(`total_dbu_dollars`)"
                    },
                    {
                      "name": "eng_type",
                      "expression": "`eng_type`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "territory_area",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(total_dbu_dollars)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  },
                  "format": {
                    "type": "number-currency",
                    "currencyCode": "USD",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                },
                "color": {
                  "fieldName": "eng_type",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Revenue by Territory ($)"
              }
            }
          },
          "position": {
            "x": 3,
            "y": 9,
            "width": 3,
            "height": 5
          }
        }
        ,
        # --- T-212 outcome tags ---
        {
          "widget": {
            "name": "kpi_outcome_mix",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_activity_impact_tags",
                  "fields": [
                    {
                      "name": "impact_tag",
                      "expression": "`impact_tag`"
                    },
                    {
                      "name": "count(*)",
                      "expression": "COUNT(*)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "impact_tag",
                  "scale": {"type": "categorical"},
                  "displayName": "Outcome tag"
                },
                "y": {
                  "fieldName": "count(*)",
                  "scale": {"type": "quantitative"},
                  "displayName": "Count"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Outcome mix (all categories)",
                "showDescription": True,
                "description": "Counts of qualitative tags across all activity categories (T-212)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 14,
            "width": 6,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_outcomes_by_category",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_activity_impact_tags",
                  "fields": [
                    {
                      "name": "category",
                      "expression": "`category`"
                    },
                    {
                      "name": "impact_tag",
                      "expression": "`impact_tag`"
                    },
                    {
                      "name": "count(*)",
                      "expression": "COUNT(*)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "category",
                  "scale": {"type": "categorical"},
                  "displayName": "Category"
                },
                "y": {
                  "fieldName": "count(*)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "percent"
                  },
                  "displayName": "Share of outcomes"
                },
                "color": {
                  "fieldName": "impact_tag",
                  "scale": {"type": "categorical"},
                  "legend": {"position": "bottom"}
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Outcomes by category (100% stacked)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 19,
            "width": 6,
            "height": 5
          }
        }
        # --- end T-212 ---
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    },
    {
      "name": "p_focus",
      "displayName": "Focus Engagements",
      "layout": [
        {
          "widget": {
            "name": "header_focus",
            "multilineTextboxSpec": {
              "lines": [
                "# Focus Engagements\n",
                "\n",
                "Multi-quarter, deep strategic engagements — the core of impact work. These are accounts where sustained advisory drives measurable transformation."
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 0,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "tbl_focus",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_detail",
                  "fields": [
                    {
                      "name": "customer",
                      "expression": "`customer`"
                    },
                    {
                      "name": "engagement_title",
                      "expression": "`engagement_title`"
                    },
                    {
                      "name": "ae",
                      "expression": "`ae`"
                    },
                    {
                      "name": "fy",
                      "expression": "`fy`"
                    },
                    {
                      "name": "engagement_status",
                      "expression": "`engagement_status`"
                    },
                    {
                      "name": "territory_area",
                      "expression": "`territory_area`"
                    },
                    {
                      "name": "total_dbu_dollars",
                      "expression": "`total_dbu_dollars`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "pivot",
              "encodings": {
                "rows": [
                  {
                    "fieldName": "customer"
                  },
                  {
                    "fieldName": "engagement_title"
                  },
                  {
                    "fieldName": "ae"
                  },
                  {
                    "fieldName": "fy"
                  },
                  {
                    "fieldName": "engagement_status"
                  },
                  {
                    "fieldName": "territory_area"
                  },
                  {
                    "fieldName": "total_dbu_dollars"
                  }
                ],
                "columns": [],
                "cell": {
                  "type": "multi-cell",
                  "fields": []
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Focus Account Details"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 2,
            "width": 6,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "pivot_focus_revenue",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_revenue",
                  "fields": [
                    {
                      "name": "account_name",
                      "expression": "`account_name`"
                    },
                    {
                      "name": "usage_date_string",
                      "expression": "`usage_date_string`"
                    },
                    {
                      "name": "sum(dbu_dollars)",
                      "expression": "SUM(`dbu_dollars`)"
                    }
                  ],
                  "cubeGroupingSets": {
                    "sets": [
                      {
                        "fieldNames": [
                          "account_name"
                        ]
                      },
                      {
                        "fieldNames": [
                          "usage_date_string"
                        ]
                      }
                    ]
                  },
                  "disaggregated": False,
                  "orders": [
                    {
                      "direction": "ASC",
                      "expression": "`account_name`"
                    },
                    {
                      "direction": "ASC",
                      "expression": "`usage_date_string`"
                    }
                  ]
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "pivot",
              "encodings": {
                "rows": [
                  {
                    "fieldName": "account_name"
                  }
                ],
                "columns": [
                  {
                    "fieldName": "usage_date_string"
                  }
                ],
                "cell": {
                  "type": "multi-cell",
                  "fields": [
                    {
                      "fieldName": "sum(dbu_dollars)",
                      "cellType": "text",
                      "format": {
                        "type": "number-currency",
                        "currencyCode": "USD",
                        "abbreviation": "none",
                        "decimalPlaces": {
                          "type": "exact",
                          "places": 0
                        },
                        "hideGroupSeparator": False
                      }
                    }
                  ]
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Focus Account Revenue by Quarter ($)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 7,
            "width": 6,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_focus_revenue",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_revenue",
                  "fields": [
                    {
                      "name": "usage_date_string",
                      "expression": "`usage_date_string`"
                    },
                    {
                      "name": "sum(dbu_dollars)",
                      "expression": "SUM(`dbu_dollars`)"
                    },
                    {
                      "name": "account_name",
                      "expression": "`account_name`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "usage_date_string",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(dbu_dollars)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-currency",
                    "currencyCode": "USD",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                },
                "color": {
                  "fieldName": "account_name",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Focus Account Revenue Trend (Quarterly)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 12,
            "width": 6,
            "height": 6
          }
        },
        {
          "widget": {
            "name": "chart_focus_growth",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_revenue",
                  "fields": [
                    {
                      "name": "usage_date_string",
                      "expression": "`usage_date_string`"
                    },
                    {
                      "name": "avg(growth_rate)",
                      "expression": "AVG(`growth_rate`)"
                    },
                    {
                      "name": "account_name",
                      "expression": "`account_name`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "usage_date_string",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "avg(growth_rate)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-percent",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                },
                "color": {
                  "fieldName": "account_name",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                },
                "label": {
                  "show": True
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Focus Account QoQ Growth Rate"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 18,
            "width": 6,
            "height": 6
          }
        }
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    },
    {
      "name": "p_oneoff",
      "displayName": "One-off Engagements",
      "layout": [
        {
          "widget": {
            "name": "header_oneoff",
            "multilineTextboxSpec": {
              "lines": [
                "# One-off Engagements\n",
                "\n",
                "Targeted, topic-specific engagements — keynotes, points of view, and advisory sessions that extend strategic reach across the portfolio."
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 0,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "chart_oneoff_formats",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff",
                  "fields": [
                    {
                      "name": "engagement_format",
                      "expression": "`engagement_format`"
                    },
                    {
                      "name": "count(*)",
                      "expression": "COUNT(`*`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "engagement_format",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "count(*)",
                  "scale": {
                    "type": "quantitative"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "One-off Engagements by Format"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 2,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_oneoff_timeline",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff",
                  "fields": [
                    {
                      "name": "fy",
                      "expression": "`fy`"
                    },
                    {
                      "name": "count(*)",
                      "expression": "COUNT(`*`)"
                    },
                    {
                      "name": "engagement_format",
                      "expression": "`engagement_format`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "fy",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "count(*)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  }
                },
                "color": {
                  "fieldName": "engagement_format",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "One-off Engagements Over Time"
              }
            }
          },
          "position": {
            "x": 3,
            "y": 2,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "tbl_oneoff",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff",
                  "fields": [
                    {
                      "name": "customer",
                      "expression": "`customer`"
                    },
                    {
                      "name": "engagement_format",
                      "expression": "`engagement_format`"
                    },
                    {
                      "name": "engagement_title",
                      "expression": "`engagement_title`"
                    },
                    {
                      "name": "ae",
                      "expression": "`ae`"
                    },
                    {
                      "name": "fy",
                      "expression": "`fy`"
                    },
                    {
                      "name": "quarter",
                      "expression": "`quarter`"
                    },
                    {
                      "name": "territory_area",
                      "expression": "`territory_area`"
                    },
                    {
                      "name": "total_dbu_dollars",
                      "expression": "`total_dbu_dollars`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "pivot",
              "encodings": {
                "rows": [
                  {
                    "fieldName": "customer"
                  },
                  {
                    "fieldName": "engagement_format"
                  },
                  {
                    "fieldName": "engagement_title"
                  },
                  {
                    "fieldName": "ae"
                  },
                  {
                    "fieldName": "fy"
                  },
                  {
                    "fieldName": "quarter"
                  },
                  {
                    "fieldName": "territory_area"
                  },
                  {
                    "fieldName": "total_dbu_dollars"
                  }
                ],
                "columns": [],
                "cell": {
                  "type": "multi-cell",
                  "fields": []
                }
              },
              "frame": {
                "showTitle": True,
                "title": "One-off Engagement Details"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 7,
            "width": 6,
            "height": 6
          }
        }
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    },
    {
      "name": "p_impact",
      "displayName": "Impact Analysis",
      "layout": [
        {
          "widget": {
            "name": "header_impact",
            "multilineTextboxSpec": {
              "lines": [
                "# Impact Analysis\n",
                "\n",
                "Measuring what changed — comparing advisor portfolio growth against the regional benchmark.\n",
                "Impact = revenue growth in strategist-engaged accounts vs. non-engaged baseline (Central region)."
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 0,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "chart_benchmark_growth",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_advisor_benchmark",
                  "fields": [
                    {
                      "name": "fiscal_year",
                      "expression": "`fiscal_year`"
                    },
                    {
                      "name": "advisor_yoy_growth",
                      "expression": "`advisor_yoy_growth`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "fiscal_year",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "advisor_yoy_growth",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-percent",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 1
                    }
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "YoY Growth: Advisor Focus Portfolio vs. Central Region"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 2,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_rev_by_type",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_accounts_yoy",
                  "fields": [
                    {
                      "name": "fiscal_year",
                      "expression": "`fiscal_year`"
                    },
                    {
                      "name": "sum(dbu_dollars)",
                      "expression": "SUM(`dbu_dollars`)"
                    },
                    {
                      "name": "engagement_type",
                      "expression": "`engagement_type`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "fiscal_year",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(dbu_dollars)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  },
                  "format": {
                    "type": "number-currency",
                    "currencyCode": "USD",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                },
                "color": {
                  "fieldName": "engagement_type",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Revenue by Engagement Type (Annual)"
              }
            }
          },
          "position": {
            "x": 3,
            "y": 2,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_all_acct_revenue",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_all_acct_revenue",
                  "fields": [
                    {
                      "name": "usage_date_string",
                      "expression": "`usage_date_string`"
                    },
                    {
                      "name": "sum(dbu_dollars)",
                      "expression": "SUM(`dbu_dollars`)"
                    },
                    {
                      "name": "account_name",
                      "expression": "`account_name`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "usage_date_string",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(dbu_dollars)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-currency",
                    "currencyCode": "USD",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                },
                "color": {
                  "fieldName": "account_name",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "All Engaged Accounts — Quarterly Revenue Trajectory"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 7,
            "width": 6,
            "height": 6
          }
        },
        {
          "widget": {
            "name": "tbl_acct_yoy",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_accounts_yoy",
                  "fields": [
                    {
                      "name": "account_name",
                      "expression": "`account_name`"
                    },
                    {
                      "name": "engagement_type",
                      "expression": "`engagement_type`"
                    },
                    {
                      "name": "fiscal_year",
                      "expression": "`fiscal_year`"
                    },
                    {
                      "name": "dbu_dollars",
                      "expression": "`dbu_dollars`"
                    },
                    {
                      "name": "yoy_growth",
                      "expression": "`yoy_growth`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "pivot",
              "encodings": {
                "rows": [
                  {
                    "fieldName": "account_name"
                  },
                  {
                    "fieldName": "engagement_type"
                  },
                  {
                    "fieldName": "fiscal_year"
                  },
                  {
                    "fieldName": "dbu_dollars"
                  },
                  {
                    "fieldName": "yoy_growth"
                  }
                ],
                "columns": [],
                "cell": {
                  "type": "multi-cell",
                  "fields": []
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Account Year-over-Year Growth"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 13,
            "width": 6,
            "height": 7
          }
        },
        {
          "widget": {
            "name": "header_impact_compare",
            "multilineTextboxSpec": {
              "lines": [
                "## Per-engagement impact: account growth vs Central region average\n",
                "\n",
                "For each engagement we anchor the account's revenue at the engagement quarter (offset 0) and compare growth in subsequent periods against the Central region's average growth over the same window. Above the regional line means the engaged account is outpacing the benchmark.\n"
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 20,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "chart_oneoff_impact",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff_impact_summary",
                  "fields": [
                    {
                      "name": "qtr_offset",
                      "expression": "`qtr_offset`"
                    },
                    {
                      "name": "avg(avg_growth)",
                      "expression": "AVG(`avg_growth`)"
                    },
                    {
                      "name": "series",
                      "expression": "`series`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "qtr_offset",
                  "scale": {
                    "type": "categorical"
                  },
                  "displayName": "qtr offset"
                },
                "y": {
                  "fieldName": "avg(avg_growth)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-percent",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  },
                  "displayName": "Avg growth vs baseline"
                },
                "color": {
                  "fieldName": "series",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "One-off engagements — advisor portfolio vs Central region (avg growth from engagement Q0)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 22,
            "width": 6,
            "height": 6
          }
        },
        {
          "widget": {
            "name": "chart_focus_impact",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_impact_summary",
                  "fields": [
                    {
                      "name": "fy_offset",
                      "expression": "`fy_offset`"
                    },
                    {
                      "name": "avg(avg_growth)",
                      "expression": "AVG(`avg_growth`)"
                    },
                    {
                      "name": "series",
                      "expression": "`series`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "fy_offset",
                  "scale": {
                    "type": "categorical"
                  },
                  "displayName": "fy offset"
                },
                "y": {
                  "fieldName": "avg(avg_growth)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-percent",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  },
                  "displayName": "Avg growth vs baseline"
                },
                "color": {
                  "fieldName": "series",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Focus engagements — advisor portfolio vs Central region (avg growth from engagement FY)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 28,
            "width": 6,
            "height": 6
          }
        },
        {
          "widget": {
            "name": "chart_oneoff_impact_median",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff_impact_summary_median",
                  "fields": [
                    {
                      "name": "qtr_offset",
                      "expression": "`qtr_offset`"
                    },
                    {
                      "name": "avg(avg_growth)",
                      "expression": "AVG(`avg_growth`)"
                    },
                    {
                      "name": "series",
                      "expression": "`series`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "qtr_offset",
                  "scale": {
                    "type": "categorical"
                  },
                  "displayName": "qtr offset"
                },
                "y": {
                  "fieldName": "avg(avg_growth)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-percent",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  },
                  "displayName": "Growth vs baseline"
                },
                "color": {
                  "fieldName": "series",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "One-off engagements — MEDIAN view (less skewed by outliers)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 34,
            "width": 6,
            "height": 6
          }
        },
        {
          "widget": {
            "name": "chart_focus_impact_median",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_impact_summary_median",
                  "fields": [
                    {
                      "name": "fy_offset",
                      "expression": "`fy_offset`"
                    },
                    {
                      "name": "avg(avg_growth)",
                      "expression": "AVG(`avg_growth`)"
                    },
                    {
                      "name": "series",
                      "expression": "`series`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "fy_offset",
                  "scale": {
                    "type": "categorical"
                  },
                  "displayName": "fy offset"
                },
                "y": {
                  "fieldName": "avg(avg_growth)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-percent",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  },
                  "displayName": "Growth vs baseline"
                },
                "color": {
                  "fieldName": "series",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Focus engagements — MEDIAN view (closed FYs only)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 40,
            "width": 6,
            "height": 6
          }
        },
        {
          "widget": {
            "name": "header_impact_detail",
            "multilineTextboxSpec": {
              "lines": [
                "## Per-engagement detail\n",
                "\n",
                "Each engagement's account growth at each post-engagement period, with the Central-region average growth over the same window and the delta. Positive delta = the engaged account outpaced the regional benchmark.\n"
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 46,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "tbl_oneoff_impact",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff_impact_detail",
                  "fields": [
                    {
                      "name": "customer",
                      "expression": "`customer`"
                    },
                    {
                      "name": "engagement_format",
                      "expression": "`engagement_format`"
                    },
                    {
                      "name": "engagement_quarter_start",
                      "expression": "`engagement_quarter_start`"
                    },
                    {
                      "name": "qtr_offset_or_fy_offset",
                      "expression": "`qtr_offset`"
                    },
                    {
                      "name": "account_dbu",
                      "expression": "`account_dbu`"
                    },
                    {
                      "name": "account_growth",
                      "expression": "`account_growth`"
                    },
                    {
                      "name": "region_growth_avg",
                      "expression": "`region_growth_avg`"
                    },
                    {
                      "name": "delta_vs_region",
                      "expression": "`delta_vs_region`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 1,
              "widgetType": "table",
              "encodings": {
                "columns": [
                  {
                    "fieldName": "customer",
                    "displayName": "Customer",
                    "type": "string"
                  },
                  {
                    "fieldName": "engagement_format",
                    "displayName": "Format",
                    "type": "string"
                  },
                  {
                    "fieldName": "engagement_quarter_start",
                    "displayName": "Eng. quarter",
                    "type": "string"
                  },
                  {
                    "fieldName": "qtr_offset_or_fy_offset",
                    "displayName": "Offset",
                    "type": "integer"
                  },
                  {
                    "fieldName": "account_dbu",
                    "displayName": "Account $DBU",
                    "format": {
                      "type": "number-currency",
                      "currencyCode": "USD",
                      "abbreviation": "compact-long",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  },
                  {
                    "fieldName": "account_growth",
                    "displayName": "Account growth",
                    "format": {
                      "type": "number-percent",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  },
                  {
                    "fieldName": "region_growth_avg",
                    "displayName": "Region (avg) growth",
                    "format": {
                      "type": "number-percent",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  },
                  {
                    "fieldName": "delta_vs_region",
                    "displayName": "Delta vs region",
                    "format": {
                      "type": "number-percent",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  }
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "One-off engagements — per-engagement growth vs Central region"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 48,
            "width": 6,
            "height": 8
          }
        },
        {
          "widget": {
            "name": "tbl_focus_impact",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_impact_detail",
                  "fields": [
                    {
                      "name": "customer",
                      "expression": "`customer`"
                    },
                    {
                      "name": "engagement_format",
                      "expression": "`engagement_format`"
                    },
                    {
                      "name": "engagement_fy_int",
                      "expression": "`engagement_fy_int`"
                    },
                    {
                      "name": "qtr_offset_or_fy_offset",
                      "expression": "`fy_offset`"
                    },
                    {
                      "name": "account_dbu",
                      "expression": "`account_dbu`"
                    },
                    {
                      "name": "account_growth",
                      "expression": "`account_growth`"
                    },
                    {
                      "name": "region_growth_avg",
                      "expression": "`region_growth_avg`"
                    },
                    {
                      "name": "delta_vs_region",
                      "expression": "`delta_vs_region`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 1,
              "widgetType": "table",
              "encodings": {
                "columns": [
                  {
                    "fieldName": "customer",
                    "displayName": "Customer",
                    "type": "string"
                  },
                  {
                    "fieldName": "engagement_format",
                    "displayName": "Format",
                    "type": "string"
                  },
                  {
                    "fieldName": "engagement_fy_int",
                    "displayName": "Eng. FY",
                    "type": "string"
                  },
                  {
                    "fieldName": "qtr_offset_or_fy_offset",
                    "displayName": "Offset",
                    "type": "integer"
                  },
                  {
                    "fieldName": "account_dbu",
                    "displayName": "Account $DBU",
                    "format": {
                      "type": "number-currency",
                      "currencyCode": "USD",
                      "abbreviation": "compact-long",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  },
                  {
                    "fieldName": "account_growth",
                    "displayName": "Account growth",
                    "format": {
                      "type": "number-percent",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  },
                  {
                    "fieldName": "region_growth_avg",
                    "displayName": "Region (avg) growth",
                    "format": {
                      "type": "number-percent",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  },
                  {
                    "fieldName": "delta_vs_region",
                    "displayName": "Delta vs region",
                    "format": {
                      "type": "number-percent",
                      "decimalPlaces": {
                        "type": "exact",
                        "places": 0
                      }
                    },
                    "type": "float"
                  }
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Focus engagements — per-engagement growth vs Central region (closed FYs only)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 56,
            "width": 6,
            "height": 8
          }
        }
        ,
        # --- T-213 UCO velocity panels ---
        # Four panels: header, KPI (% engagements with ≥1 advance within 90d),
        # bar (median days_in_current_stage per stage U1..U6), bar (count of
        # late-stage transitions per quarter), and the detail table.
        {
          "widget": {
            "name": "header_uco_velocity",
            "multilineTextboxSpec": {
              "lines": [
                "## UCO Velocity\n",
                "\n",
                "How fast accounts move U1→U6 on engagements you touched. Joins your `asq_id` to `asq_uco` → `uco_change_data` (rank=1 latest snapshot).\n",
                "`stage_advance_within_90d` = at least one stage transition (ordinal up) within 90 days of `ASQ_Start_Date`.\n"
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 64,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_uco_advance_90d_pct",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_uco_velocity_detail",
                  "fields": [
                    {
                      "name": "pct_advance_90d",
                      "expression": "COUNT(DISTINCT CASE WHEN `stage_advance_within_90d` THEN `engagement_id` END) / NULLIF(COUNT(DISTINCT `engagement_id`), 0)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "pct_advance_90d",
                  "format": {
                    "type": "number-percent",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "% engagements with stage advance ≤ 90d",
                "showDescription": True,
                "description": "Of engagements with ≥1 UCO, share where at least one UCO advanced a stage within 90 days of ASQ_Start_Date."
              }
            }
          },
          "position": {
            "x": 0,
            "y": 66,
            "width": 2,
            "height": 4
          }
        },
        {
          "widget": {
            "name": "chart_uco_median_days_in_stage",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_uco_velocity_summary",
                  "fields": [
                    {
                      "name": "stage",
                      "expression": "`stage`"
                    },
                    {
                      "name": "median_days_in_stage",
                      "expression": "`median_days_in_stage`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "stage",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "median_days_in_stage",
                  "scale": {
                    "type": "quantitative"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Median days in current stage (U1..U6)"
              }
            }
          },
          "position": {
            "x": 2,
            "y": 66,
            "width": 4,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_uco_late_transitions_by_quarter",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_uco_velocity_detail",
                  "fields": [
                    {
                      "name": "transition_quarter",
                      "expression": "`transition_quarter`"
                    },
                    {
                      "name": "late_stage_transition",
                      "expression": "`late_stage_transition`"
                    },
                    {
                      "name": "transition_count",
                      "expression": "COUNT(`uco_id`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "transition_quarter",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "transition_count",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  }
                },
                "color": {
                  "fieldName": "late_stage_transition",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Late-stage transitions per quarter (U3→U4 / U4→U5 / U5→U6) — most-recent transition only"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 71,
            "width": 6,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "tbl_uco_velocity_detail",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_uco_velocity_detail",
                  "fields": [
                    {
                      "name": "customer",
                      "expression": "`customer`"
                    },
                    {
                      "name": "engagement_id",
                      "expression": "`engagement_id`"
                    },
                    {
                      "name": "uco_id",
                      "expression": "`uco_id`"
                    },
                    {
                      "name": "fy",
                      "expression": "`fy`"
                    },
                    {
                      "name": "current_stage",
                      "expression": "`current_stage`"
                    },
                    {
                      "name": "start_stage",
                      "expression": "`start_stage`"
                    },
                    {
                      "name": "days_in_current_stage",
                      "expression": "`days_in_current_stage`"
                    },
                    {
                      "name": "stages_advanced_since_engagement_start",
                      "expression": "`stages_advanced_since_engagement_start`"
                    },
                    {
                      "name": "stage_advance_within_90d",
                      "expression": "`stage_advance_within_90d`"
                    },
                    {
                      "name": "most_recent_stage_change_date",
                      "expression": "`most_recent_stage_change_date`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 1,
              "widgetType": "table",
              "encodings": {
                "columns": [
                  {
                    "fieldName": "customer",
                    "displayName": "Customer",
                    "type": "string"
                  },
                  {
                    "fieldName": "engagement_id",
                    "displayName": "ASQ",
                    "type": "string"
                  },
                  {
                    "fieldName": "uco_id",
                    "displayName": "UCO",
                    "type": "string"
                  },
                  {
                    "fieldName": "fy",
                    "displayName": "FY",
                    "type": "string"
                  },
                  {
                    "fieldName": "current_stage",
                    "displayName": "Stage",
                    "type": "string"
                  },
                  {
                    "fieldName": "start_stage",
                    "displayName": "Start stage",
                    "type": "string"
                  },
                  {
                    "fieldName": "days_in_current_stage",
                    "displayName": "Days in stage",
                    "type": "integer"
                  },
                  {
                    "fieldName": "stages_advanced_since_engagement_start",
                    "displayName": "Stages advanced",
                    "type": "integer"
                  },
                  {
                    "fieldName": "stage_advance_within_90d",
                    "displayName": "Advanced ≤90d",
                    "type": "boolean"
                  },
                  {
                    "fieldName": "most_recent_stage_change_date",
                    "displayName": "Last change",
                    "type": "date"
                  }
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Engagement × UCO velocity detail"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 76,
            "width": 6,
            "height": 8
          }
        }
        # --- end T-213 ---
        ,
        # --- T-212 outcome tags ---
        {
          "widget": {
            "name": "tbl_top_outcomes_focus",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_activity_impact_tags",
                  "fields": [
                    {
                      "name": "title",
                      "expression": "`title`"
                    },
                    {
                      "name": "fy",
                      "expression": "`fy`"
                    },
                    {
                      "name": "impact_tag",
                      "expression": "`impact_tag`"
                    },
                    {
                      "name": "count(*)",
                      "expression": "COUNT(*)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 1,
              "widgetType": "table",
              "encodings": {
                "columns": [
                  {
                    "fieldName": "title",
                    "displayName": "Activity",
                    "type": "string"
                  },
                  {
                    "fieldName": "fy",
                    "displayName": "FY",
                    "type": "string"
                  },
                  {
                    "fieldName": "impact_tag",
                    "displayName": "Outcome tag",
                    "type": "string"
                  },
                  {
                    "fieldName": "count(*)",
                    "displayName": "Tag instances",
                    "type": "integer"
                  }
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Top outcomes per Focus account / activity"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 64,
            "width": 6,
            "height": 8
          }
        }
        # --- end T-212 ---
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    },
    {
      "name": "7e23f4ab",
      "displayName": "Global Filters",
      "layout": [
        {
          "widget": {
            "name": "8ad31edb",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_strategist_email",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "strategist_email",
                      "expression": "`strategist_email`"
                    },
                    {
                      "name": "strategist_email_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True
              },
              "widgetType": "filter-single-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "strategist_email",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_strategist_email"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 0,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "068a2236",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_type",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "engagement_type",
                      "expression": "`engagement_type`"
                    },
                    {
                      "name": "engagement_type_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True
              },
              "widgetType": "filter-single-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "engagement_type",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_type"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 4,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "4164e944",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_type",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "engagement_type",
                      "expression": "`engagement_type`"
                    },
                    {
                      "name": "engagement_type_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True
              },
              "widgetType": "filter-single-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "engagement_type",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_type"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 6,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "75263dc4",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_fy",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "fy",
                      "expression": "`fy`"
                    },
                    {
                      "name": "fy_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True
              },
              "widgetType": "filter-single-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "fy",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_fy"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "30161e94",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_status",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "engagement_status",
                      "expression": "`engagement_status`"
                    },
                    {
                      "name": "engagement_status_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True
              },
              "widgetType": "filter-single-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "engagement_status",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_status"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 8,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "faceb9a2",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_territory_region",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "territory_region",
                      "expression": "`territory_region`"
                    },
                    {
                      "name": "territory_region_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True
              },
              "widgetType": "filter-single-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "territory_region",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_territory_region"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 10,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "04b292fd",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_territory_area",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "territory_area",
                      "expression": "`territory_area`"
                    },
                    {
                      "name": "territory_area_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True
              },
              "widgetType": "filter-single-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "territory_area",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_territory_area"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 12,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "filter_engagement_format",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_format",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "engagement_format",
                      "expression": "`engagement_format`"
                    },
                    {
                      "name": "engagement_format_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True,
                "title": "Engagement format"
              },
              "widgetType": "filter-multi-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "engagement_format",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_engagement_format"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 14,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "filter_quarter",
            "queries": [
              {
                "name": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_quarter",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {
                      "name": "quarter",
                      "expression": "`quarter`"
                    },
                    {
                      "name": "quarter_associativity",
                      "expression": "COUNT_IF(`associative_filter_predicate_group`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "frame": {
                "showTitle": True,
                "title": "Quarter (engagement)"
              },
              "widgetType": "filter-multi-select",
              "encodings": {
                "fields": [
                  {
                    "fieldName": "quarter",
                    "queryName": "dashboards/01f0f51a424b1cc0bc6f5feba0c33948/datasets/01f1211b00e31b138b40bc8e12ff8573_quarter"
                  }
                ]
              }
            }
          },
          "position": {
            "x": 0,
            "y": 16,
            "width": 1,
            "height": 2
          }
        }
      ],
      "pageType": "PAGE_TYPE_GLOBAL_FILTERS",
      "layoutVersion": "GRID_V1"
    },
    # --- T-219 evangelism reach page ---
    # Inserted at the end of the pages array per coordinator conflict-avoidance
    # convention (other parallel tasks T-212/T-213/T-222 also append pages).
    # Spec ordering ("after Customer Impact, before Initiatives") is informational;
    # the coordinator may reorder pages post-merge.
    {
      "name": "p_evangelism",
      "displayName": "Evangelism reach",
      "layout": [
        {
          "widget": {
            "name": "header_evangelism",
            "multilineTextboxSpec": {
              "lines": [
                "# Evangelism reach\n",
                "\n",
                "External talks, podcasts, workshops, roundtables — the strategist's *broadcast* surface.\n",
                "Measures how far the message travelled (views, attendance) and what formats actually land. Filtered by `strategist_email` from the Global Filters page; `fy` filter narrows to a single fiscal year."
              ]
            }
          },
          "position": {
            "x": 0,
            "y": 0,
            "width": 6,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_evangelism_events_delivered",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_summary",
                  "fields": [
                    {
                      "name": "sum(events_delivered)",
                      "expression": "SUM(`events_delivered`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(events_delivered)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Events FY (delivered)",
                "showDescription": True,
                "description": "Excludes cancelled + planned"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_evangelism_total_views",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_summary",
                  "fields": [
                    {
                      "name": "sum(total_views)",
                      "expression": "SUM(`total_views`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(total_views)",
                  "format": {
                    "type": "number-plain",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Total views FY",
                "showDescription": True,
                "description": "Delivered events only"
              }
            }
          },
          "position": {
            "x": 1,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_evangelism_total_attendance",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_summary",
                  "fields": [
                    {
                      "name": "sum(total_attendance)",
                      "expression": "SUM(`total_attendance`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(total_attendance)",
                  "format": {
                    "type": "number-plain",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Total attendance FY",
                "showDescription": True,
                "description": "Sum of `participants`"
              }
            }
          },
          "position": {
            "x": 2,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_evangelism_unique_types",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_summary",
                  "fields": [
                    {
                      "name": "countdistinct(event_type)",
                      "expression": "COUNT(DISTINCT `event_type`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "countdistinct(event_type)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Unique event_types FY",
                "showDescription": True,
                "description": "Keynote / Breakout / Podcast / ..."
              }
            }
          },
          "position": {
            "x": 3,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "kpi_evangelism_planned_next_30d",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_summary",
                  "fields": [
                    {
                      "name": "sum(events_planned_next_30d)",
                      "expression": "SUM(`events_planned_next_30d`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "sum(events_planned_next_30d)"
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Planned next 30d",
                "showDescription": True,
                "description": "Leading indicator — book early"
              }
            }
          },
          "position": {
            "x": 4,
            "y": 2,
            "width": 1,
            "height": 2
          }
        },
        {
          "widget": {
            "name": "chart_evangelism_by_quarter",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_by_quarter",
                  "fields": [
                    {
                      "name": "quarter",
                      "expression": "`quarter`"
                    },
                    {
                      "name": "sum(events_count)",
                      "expression": "SUM(`events_count`)"
                    },
                    {
                      "name": "event_type",
                      "expression": "`event_type`"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "quarter",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "sum(events_count)",
                  "scale": {
                    "type": "quantitative",
                    "stackMode": "stacked"
                  }
                },
                "color": {
                  "fieldName": "event_type",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Events per quarter × event_type"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 4,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "chart_evangelism_avg_views",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_summary",
                  "fields": [
                    {
                      "name": "event_type",
                      "expression": "`event_type`"
                    },
                    {
                      "name": "avg(avg_views_per_event)",
                      "expression": "AVG(`avg_views_per_event`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "bar",
              "encodings": {
                "x": {
                  "fieldName": "event_type",
                  "scale": {
                    "type": "categorical"
                  }
                },
                "y": {
                  "fieldName": "avg(avg_views_per_event)",
                  "scale": {
                    "type": "quantitative"
                  },
                  "format": {
                    "type": "number-plain",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {
                      "type": "exact",
                      "places": 0
                    }
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Avg views per event_type"
              }
            }
          },
          "position": {
            "x": 3,
            "y": 4,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "tbl_evangelism_top_events",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_top",
                  "fields": [
                    {
                      "name": "event_name",
                      "expression": "`event_name`"
                    },
                    {
                      "name": "event_date",
                      "expression": "`event_date`"
                    },
                    {
                      "name": "event_type",
                      "expression": "`event_type`"
                    },
                    {
                      "name": "location",
                      "expression": "`location`"
                    },
                    {
                      "name": "status",
                      "expression": "`status`"
                    },
                    {
                      "name": "views",
                      "expression": "`views`"
                    },
                    {
                      "name": "attendance",
                      "expression": "`attendance`"
                    },
                    {
                      "name": "comments",
                      "expression": "`comments`"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 1,
              "widgetType": "table",
              "encodings": {
                "columns": [
                  {
                    "fieldName": "event_name",
                    "displayName": "Event",
                    "type": "string"
                  },
                  {
                    "fieldName": "event_date",
                    "displayName": "Date",
                    "type": "date"
                  },
                  {
                    "fieldName": "event_type",
                    "displayName": "Type",
                    "type": "string"
                  },
                  {
                    "fieldName": "location",
                    "displayName": "Location",
                    "type": "string"
                  },
                  {
                    "fieldName": "status",
                    "displayName": "Status",
                    "type": "string"
                  },
                  {
                    "fieldName": "views",
                    "displayName": "Views",
                    "type": "integer"
                  },
                  {
                    "fieldName": "attendance",
                    "displayName": "Attendance",
                    "type": "integer"
                  },
                  {
                    "fieldName": "comments",
                    "displayName": "Comments",
                    "type": "integer"
                  }
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Top events FY by views (deterministic: views DESC → event_date DESC → event_name ASC)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 9,
            "width": 6,
            "height": 7
          }
        },
        {
          "widget": {
            "name": "chart_evangelism_status_mix",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_by_quarter",
                  "fields": [
                    {
                      "name": "status",
                      "expression": "`status`"
                    },
                    {
                      "name": "sum(events_count)",
                      "expression": "SUM(`events_count`)"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "pie",
              "encodings": {
                "angle": {
                  "fieldName": "sum(events_count)",
                  "scale": {
                    "type": "quantitative"
                  }
                },
                "color": {
                  "fieldName": "status",
                  "scale": {
                    "type": "categorical"
                  },
                  "legend": {
                    "position": "bottom"
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Status mix (planned / delivered / cancelled)"
              }
            }
          },
          "position": {
            "x": 0,
            "y": 16,
            "width": 3,
            "height": 5
          }
        },
        {
          "widget": {
            "name": "tbl_evangelism_planned_next_30d",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_evangelism_top",
                  "fields": [
                    {
                      "name": "event_name",
                      "expression": "`event_name`"
                    },
                    {
                      "name": "event_date",
                      "expression": "`event_date`"
                    },
                    {
                      "name": "event_type",
                      "expression": "`event_type`"
                    },
                    {
                      "name": "is_planned_next_30d",
                      "expression": "`is_planned_next_30d`"
                    }
                  ],
                  "filters": [
                    {
                      "name": "is_planned_next_30d_filter",
                      "expression": "`is_planned_next_30d` = true"
                    }
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 1,
              "widgetType": "table",
              "encodings": {
                "columns": [
                  {
                    "fieldName": "event_name",
                    "displayName": "Event",
                    "type": "string"
                  },
                  {
                    "fieldName": "event_date",
                    "displayName": "Date",
                    "type": "date"
                  },
                  {
                    "fieldName": "event_type",
                    "displayName": "Type",
                    "type": "string"
                  }
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Planned in next 30 days — leading indicator",
                "showDescription": True,
                "description": "Status = 'planned' AND event_date between today and today + 30d"
              }
            }
          },
          "position": {
            "x": 3,
            "y": 16,
            "width": 3,
            "height": 5
          }
        }
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    }
    # --- end T-219 ---
    ,
    # --- T-222 relationship depth page ---
    {
      "name": "p_relationship_depth",
      "displayName": "Relationship depth",
      "layout": [
        {
          "widget": {
            "name": "header_relationship_depth",
            "multilineTextboxSpec": {
              "lines": [
                "# Relationship depth\n",
                "\n",
                "How many CXOs we engage, how often, across how many accounts — the strategist's job at any senior account. ",
                "Gap panel flags accounts where we've touched a CXO recently but have no customer engagement in flight (QBR prep view)."
              ]
            }
          },
          "position": {"x": 0, "y": 0, "width": 6, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_distinct_cxos",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_summary",
                  "fields": [
                    {"name": "sum(distinct_cxos)", "expression": "SUM(`distinct_cxos`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(distinct_cxos)"}},
              "frame": {
                "showTitle": True,
                "title": "Distinct CXOs (FY)",
                "showDescription": True,
                "description": "Unique CXO people per account in FY"
              }
            }
          },
          "position": {"x": 0, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_accounts_with_cxo",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_summary",
                  "fields": [
                    {"name": "sum(distinct_accounts_with_cxo)", "expression": "SUM(`distinct_accounts_with_cxo`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(distinct_accounts_with_cxo)"}},
              "frame": {
                "showTitle": True,
                "title": "Accounts with CXO (FY)",
                "showDescription": True,
                "description": "Distinct accounts with any CXO meeting"
              }
            }
          },
          "position": {"x": 1, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_total_exec_meetings",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_summary",
                  "fields": [
                    {"name": "sum(meetings_total)", "expression": "SUM(`meetings_total`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(meetings_total)"}},
              "frame": {
                "showTitle": True,
                "title": "Total exec meetings (FY)",
                "showDescription": True,
                "description": "All exec meetings in FY"
              }
            }
          },
          "position": {"x": 2, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_cxo_pct",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_summary",
                  "fields": [
                    {"name": "avg(cxo_pct)", "expression": "AVG(`cxo_pct`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {
                "value": {
                  "fieldName": "avg(cxo_pct)",
                  "format": {
                    "type": "number-plain",
                    "decimalPlaces": {"type": "exact", "places": 1}
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "CXO %",
                "showDescription": True,
                "description": "cxo_meetings / total"
              }
            }
          },
          "position": {"x": 3, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_meetings_tied_to_initiative",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_summary",
                  "fields": [
                    {"name": "sum(meetings_tied_to_initiative)", "expression": "SUM(`meetings_tied_to_initiative`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(meetings_tied_to_initiative)"}},
              "frame": {
                "showTitle": True,
                "title": "Meetings tied to an initiative",
                "showDescription": True,
                "description": "Cross-category — exec meetings with initiative_id set"
              }
            }
          },
          "position": {"x": 4, "y": 2, "width": 2, "height": 2}
        },
        {
          "widget": {
            "name": "heatmap_focus_account_quarter",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_per_account",
                  "fields": [
                    {"name": "customer", "expression": "`customer`"},
                    {"name": "quarter", "expression": "`quarter`"},
                    {"name": "sum(non_placeholder)", "expression": "SUM(CASE WHEN `is_placeholder` THEN 0 ELSE 1 END)"},
                    {"name": "sum(cxo_flag)", "expression": "SUM(CASE WHEN `is_placeholder` THEN 0 WHEN `is_cxo` THEN 1 ELSE 0 END)"}
                  ],
                  "filters": [
                    {
                      "expression": "`is_focus` = true"
                    }
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "heatmap",
              "encodings": {
                "x": {
                  "fieldName": "quarter",
                  "scale": {"type": "categorical"},
                  "displayName": "Quarter"
                },
                "y": {
                  "fieldName": "customer",
                  "scale": {"type": "categorical"},
                  "displayName": "Focus account"
                },
                "color": {
                  "fieldName": "sum(non_placeholder)",
                  "scale": {"type": "quantitative"},
                  "displayName": "Meetings (CXO highlighted via overlay)",
                  "legend": {"position": "bottom"}
                },
                "label": {"show": True}
              },
              "frame": {
                "showTitle": True,
                "title": "Exec meetings per Focus account × quarter (cell = meeting count; CXO count overlaid)"
              }
            }
          },
          "position": {"x": 0, "y": 4, "width": 6, "height": 7}
        },
        {
          "widget": {
            "name": "timeseries_cxo_cadence",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_per_account",
                  "fields": [
                    {"name": "meeting_month_start", "expression": "`meeting_month_start`"},
                    {"name": "cxo_label", "expression": "`cxo_label`"},
                    {"name": "count(meeting)", "expression": "SUM(CASE WHEN `is_placeholder` THEN 0 ELSE 1 END)"}
                  ],
                  "filters": [
                    {"expression": "`is_placeholder` = false"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "line",
              "encodings": {
                "x": {
                  "fieldName": "meeting_month_start",
                  "scale": {"type": "temporal"},
                  "displayName": "Month"
                },
                "y": {
                  "fieldName": "count(meeting)",
                  "scale": {"type": "quantitative"},
                  "displayName": "Meetings"
                },
                "color": {
                  "fieldName": "cxo_label",
                  "scale": {"type": "categorical"},
                  "legend": {"position": "bottom"}
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Exec meeting cadence (CXO vs non-CXO, per month)"
              }
            }
          },
          "position": {"x": 0, "y": 11, "width": 6, "height": 6}
        },
        {
          "widget": {
            "name": "tbl_relationship_gap",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_exec_meetings_gap",
                  "fields": [
                    {"name": "customer", "expression": "`customer`"},
                    {"name": "account_id", "expression": "`account_id`"},
                    {"name": "last_cxo_meeting_date", "expression": "`last_cxo_meeting_date`"},
                    {"name": "days_since_engagement", "expression": "`days_since_engagement`"}
                  ],
                  "disaggregated": True
                }
              }
            ],
            "spec": {
              "version": 3,
              "widgetType": "pivot",
              "encodings": {
                "rows": [
                  {"fieldName": "customer"},
                  {"fieldName": "account_id"},
                  {"fieldName": "last_cxo_meeting_date"},
                  {"fieldName": "days_since_engagement"}
                ],
                "columns": [],
                "cell": {"type": "multi-cell", "fields": []}
              },
              "frame": {
                "showTitle": True,
                "title": "Gap: CXO touched in last 180d, no customer engagement in same window"
              }
            }
          },
          "position": {"x": 0, "y": 17, "width": 6, "height": 6}
        }
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    }
    # --- end T-222 ---
  ]
}


# -- API helpers --------------------------------------------------------------
def update_dashboard(w: WorkspaceClient) -> None:
    """Update the existing dashboard in-place."""
    from databricks.sdk.service.dashboards import Dashboard

    payload = json.dumps(SERIALIZED_DASHBOARD)
    dashboard = Dashboard(
        display_name=DISPLAY_NAME,
        warehouse_id=WAREHOUSE_ID,
        serialized_dashboard=payload,
    )
    w.lakeview.update(dashboard_id=DASHBOARD_ID, dashboard=dashboard)
    print(f"Dashboard {DASHBOARD_ID} updated successfully.")


def create_dashboard(w: WorkspaceClient) -> None:
    """Create a new dashboard (fresh copy)."""
    from databricks.sdk.service.dashboards import Dashboard

    payload = json.dumps(SERIALIZED_DASHBOARD)
    dashboard = Dashboard(
        display_name=DISPLAY_NAME,
        warehouse_id=WAREHOUSE_ID,
        serialized_dashboard=payload,
        parent_path=PARENT_PATH,
    )
    result = w.lakeview.create(dashboard=dashboard)
    print(f"Dashboard created: {result.dashboard_id}")


# -- CLI ----------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build / update the Strategist Impact Dashboard."
    )
    parser.add_argument(
        "--create", action="store_true",
        help="Create a new dashboard instead of updating.",
    )
    parser.add_argument(
        "--profile", default=None,
        help="Databricks CLI profile to use (e.g. logfood).",
    )
    args = parser.parse_args()

    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()

    if args.create:
        create_dashboard(w)
    else:
        update_dashboard(w)


if __name__ == "__main__":
    main()
