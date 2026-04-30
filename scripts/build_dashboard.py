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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "    FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
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
        "  SELECT\n",
        "    src.account_id, src.customer, src.strategist_email,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean\n",
        "  FROM main.field_strategist_cockpit.v_engagements_unified src\n",
        "  WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "focus_engagements AS (\n",
        "  SELECT *, CAST('20' || SUBSTRING(fy_clean, 3, 2) AS INT) AS engagement_fy_int\n",
        "  FROM eng WHERE engagement_type = 'Focus' AND REGEXP_LIKE(fy_clean, '^FY[0-9]{2}$')\n",
        "),\n",
        "focus_offsets AS (\n",
        "  SELECT f.*, o.fy_offset, f.engagement_fy_int + o.fy_offset AS target_fy\n",
        "  FROM focus_engagements f CROSS JOIN (SELECT 0 AS fy_offset UNION ALL SELECT 1) o\n",
        "),\n",
        "account_fy_dbu AS (\n",
        "  SELECT fo.strategist_email, fo.account_id, fo.engagement_fy_int, fo.fy_offset, fo.target_fy,\n",
        "    SUM(c.dbu_dollars) AS account_dbu\n",
        "  FROM focus_offsets fo\n",
        "  LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id = fo.account_id AND c.date_grain = 'quarterly'\n",
        "   AND c.fiscal_year = fo.target_fy AND c.bu1 = 'Central'\n",
        "  GROUP BY 1,2,3,4,5\n",
        "),\n",
        "region_fy_dbu AS (\n",
        "  SELECT c.fiscal_year AS target_fy, AVG(annual_dbu) AS region_avg_dbu\n",
        "  FROM (\n",
        "    SELECT account_id, fiscal_year, SUM(dbu_dollars) AS annual_dbu\n",
        "    FROM main.gtm_gold.rpt_c360_overview_unpivoted WHERE date_grain='quarterly' AND bu1='Central'\n",
        "    GROUP BY 1, 2\n",
        "  ) c GROUP BY 1\n",
        "),\n",
        "joined AS (\n",
        "  SELECT ad.strategist_email, ad.account_id, ad.engagement_fy_int, ad.fy_offset,\n",
        "    try_divide(ad.account_dbu - FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(ad.account_dbu) OVER (PARTITION BY ad.account_id, ad.engagement_fy_int ORDER BY ad.fy_offset)) AS account_growth,\n",
        "    try_divide(rd.region_avg_dbu - FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset),\n",
        "               FIRST_VALUE(rd.region_avg_dbu) OVER (PARTITION BY ad.engagement_fy_int ORDER BY ad.fy_offset)) AS region_growth\n",
        "  FROM account_fy_dbu ad LEFT JOIN region_fy_dbu rd ON rd.target_fy = ad.target_fy\n",
        ")\n",
        "SELECT CAST(fy_offset AS STRING) AS fy_offset, 'Advisor portfolio (avg)' AS series, AVG(account_growth) AS avg_growth, COUNT(DISTINCT account_id) AS n_accounts\n",
        "FROM joined WHERE strategist_email IS NOT NULL AND account_growth IS NOT NULL GROUP BY fy_offset\n",
        "UNION ALL\n",
        "SELECT CAST(fy_offset AS STRING) AS fy_offset, 'Central region (avg)' AS series, AVG(region_growth) AS avg_growth, NULL AS n_accounts\n",
        "FROM joined WHERE region_growth IS NOT NULL GROUP BY fy_offset\n",
        "ORDER BY fy_offset, series\n"
      ]
    }
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
        }
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
    }
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
