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

# Attribution windows for revenue datasets (T-214).
# Rationale: a wide `fiscal_year BETWEEN 2024 AND 2027` filter includes years
# before the engagement happened, which conflates tenure with impact. The
# windows below restrict each engagement's revenue contribution to the period
# in which the strategist could plausibly have moved the number.
#
# One-off engagements: revenue from quarter +1..+4 inclusive (one full year
# AFTER the engagement quarter — exclude the engagement quarter itself so we
# measure influence, not baseline).
# Focus engagements: revenue from engagement_FY..engagement_FY+1 inclusive
# (the engagement FY plus the immediate follow-on year — Focus accounts run
# multi-quarter, so the engagement FY revenue *is* part of the impact window).
ONEOFF_WINDOW_QUARTERS = (1, 4)  # engagement_quarter +1 .. +4 inclusive
FOCUS_WINDOW_FYS = (0, 1)        # engagement_FY .. engagement_FY+1 inclusive


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
        # T-214: windowed attribution — only the engagement FY and FY+1 contribute.
        # Old wide-window WHERE: c.fiscal_year BETWEEN 2024 AND 2027 (rollback: see commit message).
        "WITH eng AS (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot, fy),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "),\n",
        "focus_eng AS (\n",
        "  -- T-214 windowed: derive engagement_fy_int and window bounds per Focus engagement.\n",
        "  SELECT e.*, \n",
        "    CAST('20' || SUBSTRING(e.fy_clean, 3, 2) AS INT) AS engagement_fy_int\n",
        "  FROM eng e\n",
        "  WHERE e.engagement_type = 'Focus'\n",
        "    AND e.account_id IS NOT NULL\n",
        "    AND REGEXP_LIKE(e.fy_clean, '^FY[0-9]{2}$')\n",
        ")\n",
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
        "FROM focus_eng e\n",
        "LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "  ON e.account_id = c.account_id\n",
        # T-214: windowed — restrict to engagement_FY..engagement_FY+1 inclusive.
        "WHERE c.date_grain = 'quarterly'\n",
        "  AND c.bu1 = 'Central'\n",
        "  AND c.fiscal_year BETWEEN e.engagement_fy_int AND e.engagement_fy_int + 1\n",
        "GROUP BY e.customer, c.usage_date_string, c.fiscal_year, c.usage_date_fiscal_quarter_start, c.usage_date\n",
        "ORDER BY e.customer, c.usage_date_fiscal_quarter_start\n"
      ]
    },
    {
      "name": "ds_advisor_benchmark",
      "displayName": "advisor_vs_region_benchmark",
      "queryLines": [
        # T-214: windowed advisor side — each Focus engagement contributes only
        # in FY..FY+1. Region side stays Central-wide so YoY comparison remains
        # apples-to-apples on the fiscal_years that the advisor portfolio touches.
        # Old wide-window filter: c.fiscal_year BETWEEN 2024 AND 2027 (rollback: see commit msg).
        "WITH eng AS (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot, fy),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "),\n",
        "focus_eng AS (\n",
        "  -- T-214 windowed: bound each Focus engagement to FY..FY+1.\n",
        "  SELECT e.*,\n",
        "    CAST('20' || SUBSTRING(e.fy_clean, 3, 2) AS INT) AS engagement_fy_int\n",
        "  FROM eng e\n",
        "  WHERE e.engagement_type = 'Focus'\n",
        "    AND e.account_id IS NOT NULL\n",
        "    AND REGEXP_LIKE(e.fy_clean, '^FY[0-9]{2}$')\n",
        "),\n",
        "advisor_windowed AS (\n",
        "  -- T-214 windowed: filter c.fiscal_year by the per-engagement window BEFORE SUM.\n",
        "  SELECT\n",
        "    'Focus' AS portfolio_type,\n",
        "    c.fiscal_year,\n",
        "    ROUND(SUM(c.dbu_dollars)) AS advisor_total_dbu_dollars\n",
        "  FROM focus_eng e\n",
        "  LEFT JOIN main.gtm_gold.rpt_c360_overview_unpivoted c ON e.account_id = c.account_id\n",
        "  WHERE c.date_grain = 'quarterly' AND c.bu1 = 'Central'\n",
        "    AND c.fiscal_year BETWEEN e.engagement_fy_int AND e.engagement_fy_int + 1\n",
        "  GROUP BY c.fiscal_year\n",
        "),\n",
        "advisor AS (\n",
        "  SELECT\n",
        "    portfolio_type, fiscal_year, advisor_total_dbu_dollars,\n",
        "    try_divide(\n",
        "      (advisor_total_dbu_dollars - LAG(advisor_total_dbu_dollars) OVER (ORDER BY fiscal_year)),\n",
        "      LAG(advisor_total_dbu_dollars) OVER (ORDER BY fiscal_year)\n",
        "    ) AS advisor_yoy_growth\n",
        "  FROM advisor_windowed\n",
        "),\n",
        "region AS (\n",
        "  SELECT\n",
        "    fiscal_year AS region_fiscal_year,\n",
        "    ROUND(SUM(dbu_dollars)) AS region_total_dbu_dollars,\n",
        "    try_divide(\n",
        "      (SUM(dbu_dollars) - LAG(SUM(dbu_dollars)) OVER (ORDER BY fiscal_year)),\n",
        "      LAG(SUM(dbu_dollars)) OVER (ORDER BY fiscal_year)\n",
        "    ) AS region_yoy_growth\n",
        "  FROM main.gtm_gold.rpt_c360_overview_unpivoted\n",
        # T-214: region baseline stays at the static 2024..2027 envelope — region
        # benchmark is a "what would average have looked like" comparison; varying
        # its window per engagement would defeat the apples-to-apples intent.
        "  WHERE date_grain = 'quarterly' AND fiscal_year BETWEEN 2024 AND 2027 AND bu1 = 'Central'\n",
        "  GROUP BY fiscal_year\n",
        ")\n",
        "SELECT * FROM advisor\n",
        "JOIN region ON advisor.fiscal_year = region.region_fiscal_year\n"
      ]
    },
    {
      "name": "ds_accounts_yoy",
      "displayName": "accounts_yoy_growth",
      "queryLines": [
        # T-214: windowed attribution per engagement type. Focus: FY..FY+1.
        # One-off: revenue from the four quarters after the engagement quarter
        # (mapped back to fiscal_year via usage_date_fiscal_quarter_start). Each
        # engagement contributes revenue ONLY in its own window — orphans
        # (missing fy/quarter or NULL account_id) are excluded.
        # Old wide-window filter: c.fiscal_year BETWEEN 2024 AND 2027.
        "WITH eng AS (\n",
        "  SELECT\n",
        "    src.* EXCEPT(engagement_type, engagement_format, quarter, account_executive, ae_snapshot, fy),\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_format, '')), '[\\r\\n]', ''), '') AS engagement_format,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean,\n",
        "    COALESCE(src.account_executive, src.ae_snapshot) AS ae\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "  WHERE src.account_id IS NOT NULL\n",
        "),\n",
        "focus_eng AS (\n",
        "  SELECT e.*, CAST('20'||SUBSTRING(e.fy_clean,3,2) AS INT) AS engagement_fy_int\n",
        "  FROM eng e\n",
        "  WHERE e.engagement_type = 'Focus' AND REGEXP_LIKE(e.fy_clean,'^FY[0-9]{2}$')\n",
        "),\n",
        "oneoff_eng AS (\n",
        "  SELECT e.*,\n",
        "    make_date(CAST('20'||SUBSTRING(e.quarter,3,2) AS INT)-1,\n",
        "      CASE SUBSTRING(e.quarter,6,1) WHEN '1' THEN 2 WHEN '2' THEN 5 WHEN '3' THEN 8 WHEN '4' THEN 11 END, 1) AS engagement_quarter_start\n",
        "  FROM eng e\n",
        "  WHERE e.engagement_type = 'One-off' AND REGEXP_LIKE(e.quarter,'^FY[0-9]{2}Q[1-4]$')\n",
        "),\n",
        # T-214: windowed Focus contribution (FY..FY+1).
        "focus_rev AS (\n",
        "  SELECT e.customer, e.engagement_type, e.engagement_format, c.fiscal_year, c.dbu_dollars\n",
        "  FROM focus_eng e\n",
        "  JOIN main.gtm_gold.rpt_c360_overview_unpivoted c ON e.account_id = c.account_id\n",
        "  WHERE c.date_grain='quarterly' AND c.bu1='Central'\n",
        "    AND c.fiscal_year BETWEEN e.engagement_fy_int AND e.engagement_fy_int + 1\n",
        "),\n",
        # T-214: windowed One-off contribution (engagement_quarter +1..+4 by date).
        "oneoff_rev AS (\n",
        "  SELECT e.customer, e.engagement_type, e.engagement_format, c.fiscal_year, c.dbu_dollars\n",
        "  FROM oneoff_eng e\n",
        "  JOIN main.gtm_gold.rpt_c360_overview_unpivoted c ON e.account_id = c.account_id\n",
        "  WHERE c.date_grain='quarterly' AND c.bu1='Central'\n",
        "    AND c.usage_date_fiscal_quarter_start BETWEEN add_months(e.engagement_quarter_start, 3) AND add_months(e.engagement_quarter_start, 12)\n",
        "),\n",
        "rev_unioned AS (\n",
        "  SELECT * FROM focus_rev UNION ALL SELECT * FROM oneoff_rev\n",
        ")\n",
        "SELECT\n",
        "  customer AS account_name,\n",
        "  engagement_type,\n",
        "  engagement_format,\n",
        "  fiscal_year,\n",
        "  ROUND(SUM(dbu_dollars)) AS dbu_dollars,\n",
        "  try_divide(\n",
        "    (SUM(dbu_dollars) - LAG(SUM(dbu_dollars)) OVER (PARTITION BY customer ORDER BY fiscal_year)),\n",
        "    LAG(SUM(dbu_dollars)) OVER (PARTITION BY customer ORDER BY fiscal_year)\n",
        "  ) AS yoy_growth\n",
        "FROM rev_unioned\n",
        "GROUP BY customer, engagement_type, engagement_format, fiscal_year\n",
        "ORDER BY customer, fiscal_year\n"
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
        # T-214: windowed attribution — offsets restricted to the
        # ONEOFF_WINDOW_QUARTERS range (+1..+4). Offset 0 (the engagement
        # quarter) is the growth baseline anchor — kept in account_dbu / region_dbu
        # so FIRST_VALUE in `joined` has something to divide against, then dropped
        # from the final SELECT so reported series only cover the in-window
        # offsets. This was previously offsets 0..4 in the final output, which
        # leaked baseline noise into the impact summary.
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
        # T-214: offsets 0..4 — 0 retained as baseline anchor for growth FIRST_VALUE;
        # final SELECT drops offset 0 so only +1..+4 (ONEOFF_WINDOW_QUARTERS) ships.
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
        # T-214: WHERE qtr_offset BETWEEN 1 AND 4 — drop baseline (offset 0) from reported series.
        "SELECT CAST(qtr_offset AS STRING) AS qtr_offset, 'Advisor portfolio (avg)' AS series, AVG(account_growth) AS avg_growth, COUNT(DISTINCT account_id) AS n_accounts\n",
        "FROM joined WHERE strategist_email IS NOT NULL AND account_growth IS NOT NULL AND qtr_offset BETWEEN 1 AND 4 GROUP BY qtr_offset\n",
        "UNION ALL\n",
        "SELECT CAST(qtr_offset AS STRING) AS qtr_offset, 'Central region (avg)' AS series, AVG(region_growth) AS avg_growth, NULL AS n_accounts\n",
        "FROM joined WHERE region_growth IS NOT NULL AND qtr_offset BETWEEN 1 AND 4 GROUP BY qtr_offset\n",
        "ORDER BY qtr_offset, series\n"
      ]
    },
    {
      "name": "ds_focus_impact_summary",
      "displayName": "focus_impact_summary",
      "queryLines": [
        # T-214: windowed attribution — offsets 0..1 already match
        # FOCUS_WINDOW_FYS = (0, 1) by construction. Offset 0 = engagement FY
        # baseline (kept as growth anchor); offset 1 = engagement FY + 1
        # (the in-window follow-on year). No structural change needed here vs.
        # the pre-T-214 version — this comment documents the alignment so it
        # doesn't drift later.
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
        # T-214: offsets 0..1 = FOCUS_WINDOW_FYS (0, 1). Closed-FY filter
        # complements the window — drops in-progress FY rows for fairness.
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
    # --- T-214 windowed attribution: total influenced revenue tile ---
    {
      "name": "ds_influenced_revenue_windowed",
      "displayName": "influenced_revenue_windowed",
      "queryLines": [
        # T-214: total influenced revenue across all engaged accounts, summed
        # over the union of in-window (account_id, fiscal_quarter_start) pairs.
        # Dedupes quarters that fall into multiple engagement windows
        # (one account engaged via Focus AND One-off → each quarter counted once).
        # NULL account_id (orphan manual rows) is excluded via `account_id IS NOT NULL`.
        "WITH eng AS (\n",
        "  SELECT src.account_id,\n",
        "    NULLIF(REGEXP_REPLACE(TRIM(COALESCE(src.engagement_type, '')), '[\\r\\n]', ''), '') AS engagement_type,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.quarter, '')), '-', ''), '[\\r\\n]', ''), '') AS quarter,\n",
        "    NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(src.fy, '')), '-', ''), '[\\r\\n]', ''), '') AS fy_clean\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified src\n",
        "  WHERE src.account_id IS NOT NULL\n",
        "),\n",
        # T-214: Focus windows = FY..FY+1; collect every quarter falling in any Focus window.
        "focus_target_qtrs AS (\n",
        "  SELECT DISTINCT f.account_id, c.usage_date_fiscal_quarter_start, c.fiscal_year\n",
        "  FROM (\n",
        "    SELECT DISTINCT account_id, CAST('20'||SUBSTRING(fy_clean,3,2) AS INT) AS engagement_fy_int\n",
        "    FROM eng WHERE engagement_type='Focus' AND REGEXP_LIKE(fy_clean,'^FY[0-9]{2}$')\n",
        "  ) f\n",
        "  JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id = f.account_id\n",
        "   AND c.fiscal_year BETWEEN f.engagement_fy_int AND f.engagement_fy_int + 1\n",
        "   AND c.date_grain='quarterly' AND c.bu1='Central'\n",
        "),\n",
        # T-214: One-off windows = engagement_quarter +1..+4; collect every quarter in any one-off window.
        "oneoff_target_qtrs AS (\n",
        "  SELECT DISTINCT o.account_id, c.usage_date_fiscal_quarter_start, c.fiscal_year\n",
        "  FROM (\n",
        "    SELECT DISTINCT account_id,\n",
        "      make_date(CAST('20'||SUBSTRING(quarter,3,2) AS INT)-1,\n",
        "        CASE SUBSTRING(quarter,6,1) WHEN '1' THEN 2 WHEN '2' THEN 5 WHEN '3' THEN 8 WHEN '4' THEN 11 END, 1) AS engagement_quarter_start\n",
        "    FROM eng WHERE engagement_type='One-off' AND REGEXP_LIKE(quarter,'^FY[0-9]{2}Q[1-4]$')\n",
        "  ) o\n",
        "  JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "    ON c.account_id = o.account_id\n",
        "   AND c.usage_date_fiscal_quarter_start BETWEEN add_months(o.engagement_quarter_start, 3) AND add_months(o.engagement_quarter_start, 12)\n",
        "   AND c.date_grain='quarterly' AND c.bu1='Central'\n",
        "),\n",
        # T-214: UNION (not UNION ALL) — dedupe (account_id, quarter) pairs that
        # fall in BOTH a Focus and a One-off window for the same account.
        "all_periods AS (\n",
        "  SELECT account_id, usage_date_fiscal_quarter_start, fiscal_year FROM focus_target_qtrs\n",
        "  UNION\n",
        "  SELECT account_id, usage_date_fiscal_quarter_start, fiscal_year FROM oneoff_target_qtrs\n",
        ")\n",
        "SELECT\n",
        "  p.fiscal_year AS fy,\n",
        "  ROUND(SUM(c.dbu_dollars)) AS total_influenced_revenue_windowed,\n",
        "  COUNT(DISTINCT p.account_id) AS n_engaged_accounts\n",
        "FROM all_periods p\n",
        "JOIN main.gtm_gold.rpt_c360_overview_unpivoted c\n",
        "  ON c.account_id = p.account_id\n",
        " AND c.usage_date_fiscal_quarter_start = p.usage_date_fiscal_quarter_start\n",
        "WHERE c.date_grain='quarterly' AND c.bu1='Central'\n",
        "GROUP BY p.fiscal_year\n",
        "ORDER BY p.fiscal_year\n"
      ]
    },
    # --- end T-214 windowed attribution tile dataset ---
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
    ,
    # --- T-221 initiative outcomes datasets ---
    # FY x status aggregate over `initiatives`. `last_activity_at` per row is the
    # max of i.last_activity_at and the latest exec_meetings.updated_at linked
    # via initiative_id — so an exec meeting against the initiative counts as
    # activity even if the initiative row itself wasn't touched. Stalled count
    # is materialised here so the KPI tile can SUM across rows that match the
    # active strategist_email / fy filter (threshold 30 days; on_hold + paused
    # are intentional pauses and NEVER count as stalled).
    {
      "name": "ds_initiatives_status",
      "displayName": "initiatives_status",
      "queryLines": [
        "WITH em_activity AS (\n",
        "  SELECT initiative_id, MAX(updated_at) AS em_last_updated\n",
        "  FROM main.field_strategist_cockpit.exec_meetings\n",
        "  WHERE initiative_id IS NOT NULL\n",
        "  GROUP BY initiative_id\n",
        "),\n",
        "initiative_activity AS (\n",
        "  SELECT\n",
        "    i.strategist_email,\n",
        "    i.fy,\n",
        "    i.status,\n",
        "    i.id AS initiative_id,\n",
        "    GREATEST(\n",
        "      COALESCE(i.last_activity_at, i.updated_at, i.created_at),\n",
        "      COALESCE(em.em_last_updated, CAST('1900-01-01' AS TIMESTAMP))\n",
        "    ) AS row_last_activity_at\n",
        "  FROM main.field_strategist_cockpit.initiatives i\n",
        "  LEFT JOIN em_activity em ON em.initiative_id = i.id\n",
        "  WHERE i.strategist_email IS NOT NULL\n",
        ")\n",
        "SELECT\n",
        "  strategist_email,\n",
        "  fy,\n",
        "  status,\n",
        "  COUNT(*) AS initiatives_count,\n",
        "  MAX(row_last_activity_at) AS last_activity_at,\n",
        "  SUM(\n",
        "    CASE\n",
        "      WHEN status = 'active'\n",
        "       AND row_last_activity_at IS NOT NULL\n",
        "       AND DATEDIFF(current_date(), CAST(row_last_activity_at AS DATE)) > 30\n",
        "      THEN 1 ELSE 0\n",
        "    END\n",
        "  ) AS stalled_count,\n",
        "  SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_count,\n",
        "  SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) AS complete_count,\n",
        "  SUM(CASE WHEN status = 'on_hold' THEN 1 ELSE 0 END) AS on_hold_count,\n",
        "  SUM(CASE WHEN status = 'paused' THEN 1 ELSE 0 END) AS paused_count\n",
        "FROM initiative_activity\n",
        "GROUP BY strategist_email, fy, status\n",
        "ORDER BY strategist_email, fy, status\n"
      ]
    },
    # Initiative-level detail. One row per initiative. `linked_exec_meeting_count`
    # is the COUNT of exec_meetings.initiative_id = i.id (always integer, 0 when
    # no linkage — never NULL). `linked_customer_engagement_count` is the
    # *practical proxy* the spec calls for: exec_meetings rows with BOTH
    # initiative_id AND asq_id set (i.e. an exec meeting that ties the
    # initiative to an ASQ). The unified engagements view does not currently
    # carry initiative_id, so direct join is not possible — flagged in
    # `docs/tasks/todo.md` T-221 as a known proxy. `has_cxo_sponsorship`
    # flips TRUE when ≥1 linked exec_meeting has is_cxo=true.
    {
      "name": "ds_initiatives_with_links",
      "displayName": "initiatives_with_links",
      "queryLines": [
        "WITH em_per_initiative AS (\n",
        "  SELECT\n",
        "    initiative_id,\n",
        "    COUNT(*) AS exec_meeting_count,\n",
        "    SUM(CASE WHEN asq_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_customer_engagement_count,\n",
        "    SUM(CASE WHEN is_cxo = TRUE THEN 1 ELSE 0 END) AS cxo_meeting_count,\n",
        "    MAX(updated_at) AS em_last_updated\n",
        "  FROM main.field_strategist_cockpit.exec_meetings\n",
        "  WHERE initiative_id IS NOT NULL\n",
        "  GROUP BY initiative_id\n",
        ")\n",
        "SELECT\n",
        "  i.strategist_email,\n",
        "  i.id AS initiative_id,\n",
        "  i.name,\n",
        "  i.feip_ticket,\n",
        "  i.status,\n",
        "  i.fy,\n",
        "  i.actionable_outcome,\n",
        "  COALESCE(em.exec_meeting_count, 0) AS linked_exec_meeting_count,\n",
        "  COALESCE(em.linked_customer_engagement_count, 0) AS linked_customer_engagement_count,\n",
        "  COALESCE(em.cxo_meeting_count, 0) AS cxo_meeting_count,\n",
        "  CASE WHEN COALESCE(em.cxo_meeting_count, 0) > 0 THEN TRUE ELSE FALSE END AS has_cxo_sponsorship,\n",
        "  GREATEST(\n",
        "    COALESCE(i.last_activity_at, i.updated_at, i.created_at),\n",
        "    COALESCE(em.em_last_updated, CAST('1900-01-01' AS TIMESTAMP))\n",
        "  ) AS last_activity_at,\n",
        "  DATEDIFF(\n",
        "    current_date(),\n",
        "    CAST(\n",
        "      GREATEST(\n",
        "        COALESCE(i.last_activity_at, i.updated_at, i.created_at),\n",
        "        COALESCE(em.em_last_updated, CAST('1900-01-01' AS TIMESTAMP))\n",
        "      ) AS DATE\n",
        "    )\n",
        "  ) AS days_since_last_activity,\n",
        "  CASE\n",
        "    WHEN i.status = 'active'\n",
        "     AND DATEDIFF(\n",
        "           current_date(),\n",
        "           CAST(\n",
        "             GREATEST(\n",
        "               COALESCE(i.last_activity_at, i.updated_at, i.created_at),\n",
        "               COALESCE(em.em_last_updated, CAST('1900-01-01' AS TIMESTAMP))\n",
        "             ) AS DATE\n",
        "           )\n",
        "         ) > 30\n",
        "    THEN TRUE ELSE FALSE\n",
        "  END AS is_stalled\n",
        "FROM main.field_strategist_cockpit.initiatives i\n",
        "LEFT JOIN em_per_initiative em ON em.initiative_id = i.id\n",
        "WHERE i.strategist_email IS NOT NULL\n",
        "ORDER BY i.fy DESC, i.status, i.name\n"
      ]
    }
    # --- end T-221 ---
    ,
    # --- T-223 portfolio readiness datasets ---
    # Five "Monday morning worklist" datasets. Each returns a small row count
    # (the page is a worklist, not analytics). All tenancy-filtered by
    # strategist_email everywhere. focused_account_planning + initiatives are
    # empty until T-217 --apply lands; the queries still parse + return zero
    # rows in that interim state.
    {
      "name": "ds_focus_without_plan",
      "displayName": "focus_without_plan",
      "queryLines": [
        "-- T-223: Focus accounts with no focused_account_planning row in the\n",
        "-- last 90 days. Focus-only by design (Light/non-Focus do NOT appear).\n",
        "-- Brand-new Focus engagements (<90d old) intentionally surface — they\n",
        "-- need a plan. days_since_engagement_created is a soft signal capped\n",
        "-- at 90 so the column reads sensibly even for older accounts.\n",
        "WITH focus_eng AS (\n",
        "  SELECT\n",
        "    e.strategist_email,\n",
        "    e.customer,\n",
        "    e.account_id,\n",
        "    COALESCE(e.account_executive, e.ae_snapshot) AS ae,\n",
        "    MAX(e.ASQ_Start_Date) AS last_engagement_date,\n",
        "    MIN(e.ASQ_Start_Date) AS first_engagement_date\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified e\n",
        "  WHERE e.strategist_email IS NOT NULL\n",
        "    AND e.account_id IS NOT NULL\n",
        "    AND NULLIF(REGEXP_REPLACE(TRIM(COALESCE(e.engagement_type, '')), '[\\r\\n]', ''), '') = 'Focus'\n",
        "  GROUP BY e.strategist_email, e.customer, e.account_id, COALESCE(e.account_executive, e.ae_snapshot)\n",
        "),\n",
        "last_plan AS (\n",
        "  -- Most-recent planning session per (strategist, account), regardless of\n",
        "  -- age. Used to compute days_since_last_plan; NULL when no plan ever.\n",
        "  SELECT\n",
        "    strategist_email,\n",
        "    account_id,\n",
        "    MAX(session_date) AS last_plan_date\n",
        "  FROM main.field_strategist_cockpit.focused_account_planning\n",
        "  WHERE strategist_email IS NOT NULL AND account_id IS NOT NULL\n",
        "  GROUP BY strategist_email, account_id\n",
        "),\n",
        "recent_plans AS (\n",
        "  SELECT DISTINCT strategist_email, account_id\n",
        "  FROM main.field_strategist_cockpit.focused_account_planning\n",
        "  WHERE strategist_email IS NOT NULL\n",
        "    AND account_id IS NOT NULL\n",
        "    AND session_date >= DATE_SUB(current_date(), 90)\n",
        ")\n",
        "SELECT\n",
        "  f.strategist_email,\n",
        "  f.customer,\n",
        "  f.account_id,\n",
        "  f.ae,\n",
        "  f.last_engagement_date,\n",
        "  CASE WHEN lp.last_plan_date IS NOT NULL\n",
        "       THEN DATEDIFF(current_date(), lp.last_plan_date) END AS days_since_last_plan,\n",
        "  LEAST(COALESCE(DATEDIFF(current_date(), f.first_engagement_date), 90), 90) AS days_since_engagement_created\n",
        "FROM focus_eng f\n",
        "LEFT JOIN last_plan lp\n",
        "  ON lp.strategist_email = f.strategist_email AND lp.account_id = f.account_id\n",
        "LEFT ANTI JOIN recent_plans rp\n",
        "  ON rp.strategist_email = f.strategist_email AND rp.account_id = f.account_id\n",
        "ORDER BY f.last_engagement_date DESC NULLS LAST\n"
      ]
    },
    {
      "name": "ds_focus_without_engagement",
      "displayName": "focus_without_engagement",
      "queryLines": [
        "-- T-223: Focus accounts with no customer_engagement in the current\n",
        "-- fiscal quarter. FY runs Feb->Jan: quarter = ((MONTH - 2 + 12) % 12) / 3 + 1.\n",
        "-- Quarter strings are normalised (strip dashes/whitespace) since source\n",
        "-- data has both 'FY26-Q1' and 'FY26Q1' forms.\n",
        "WITH current_fq AS (\n",
        "  SELECT\n",
        "    CONCAT(\n",
        "      'FY', LPAD(MOD(CASE WHEN MONTH(current_date()) >= 2 THEN YEAR(current_date()) + 1 ELSE YEAR(current_date()) END, 100), 2, '0'),\n",
        "      'Q', CAST(((MOD(MONTH(current_date()) - 2 + 12, 12)) DIV 3) + 1 AS STRING)\n",
        "    ) AS cq\n",
        "),\n",
        "focus_accounts AS (\n",
        "  SELECT\n",
        "    e.strategist_email,\n",
        "    e.customer,\n",
        "    e.account_id,\n",
        "    MAX(COALESCE(e.account_executive, e.ae_snapshot)) AS ae,\n",
        "    MAX(e.ASQ_Start_Date) AS last_engagement_date\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified e\n",
        "  WHERE e.strategist_email IS NOT NULL\n",
        "    AND e.account_id IS NOT NULL\n",
        "    AND NULLIF(REGEXP_REPLACE(TRIM(COALESCE(e.engagement_type, '')), '[\\r\\n]', ''), '') = 'Focus'\n",
        "  GROUP BY e.strategist_email, e.customer, e.account_id\n",
        "),\n",
        "engagements_in_current_q AS (\n",
        "  SELECT DISTINCT\n",
        "    e.strategist_email,\n",
        "    e.account_id\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified e\n",
        "  CROSS JOIN current_fq cfq\n",
        "  WHERE e.strategist_email IS NOT NULL\n",
        "    AND e.account_id IS NOT NULL\n",
        "    AND NULLIF(REGEXP_REPLACE(REPLACE(TRIM(COALESCE(e.quarter, '')), '-', ''), '[\\r\\n]', ''), '') = cfq.cq\n",
        ")\n",
        "SELECT\n",
        "  f.strategist_email,\n",
        "  f.customer,\n",
        "  f.account_id,\n",
        "  f.ae,\n",
        "  f.last_engagement_date,\n",
        "  DATEDIFF(current_date(), f.last_engagement_date) AS days_since_last_engagement\n",
        "FROM focus_accounts f\n",
        "LEFT ANTI JOIN engagements_in_current_q c\n",
        "  ON c.strategist_email = f.strategist_email AND c.account_id = f.account_id\n",
        "ORDER BY f.last_engagement_date DESC NULLS LAST\n"
      ]
    },
    {
      "name": "ds_open_asqs_without_next_steps",
      "displayName": "open_asqs_without_next_steps",
      "queryLines": [
        "-- T-223: Open ASQs with empty/null next_steps for >=14 days. 'Open' here\n",
        "-- is engagement_status IN ('In Progress','New','Approved') (the actual\n",
        "-- enum in v_customer_engagements_unified — see DESCRIBE). Whitespace-only\n",
        "-- next_steps counts as empty. Tightly bounded — expected <=10 rows; more\n",
        "-- means hygiene problem.\n",
        "SELECT\n",
        "  e.strategist_email,\n",
        "  e.customer,\n",
        "  e.account_id,\n",
        "  COALESCE(e.account_executive, e.ae_snapshot) AS ae,\n",
        "  e.asq_id,\n",
        "  e.engagement_title,\n",
        "  e.engagement_status,\n",
        "  e.ASQ_Start_Date,\n",
        "  DATEDIFF(current_date(), e.ASQ_Start_Date) AS days_since_start,\n",
        "  e.asq_url\n",
        "FROM main.field_strategist_cockpit.v_customer_engagements_unified e\n",
        "WHERE e.strategist_email IS NOT NULL\n",
        "  AND e.engagement_status IN ('In Progress', 'New', 'Approved')\n",
        "  AND (e.next_steps IS NULL OR LENGTH(TRIM(e.next_steps)) = 0)\n",
        "  AND e.ASQ_Start_Date IS NOT NULL\n",
        "  AND DATEDIFF(current_date(), e.ASQ_Start_Date) >= 14\n",
        "ORDER BY days_since_start DESC\n"
      ]
    },
    {
      "name": "ds_stalled_initiatives",
      "displayName": "stalled_initiatives",
      "queryLines": [
        "-- T-223: Initiatives with last_activity_at > 30d ago AND status='active'.\n",
        "-- on_hold / paused are INTENTIONAL pauses, not stalled — excluded.\n",
        "-- Case-insensitive match on status to absorb 'Active' vs 'active'.\n",
        "SELECT\n",
        "  strategist_email,\n",
        "  id AS initiative_id,\n",
        "  name,\n",
        "  status,\n",
        "  fy,\n",
        "  feip_ticket,\n",
        "  next_steps,\n",
        "  last_activity_at,\n",
        "  DATEDIFF(current_date(), CAST(last_activity_at AS DATE)) AS days_since_last_activity\n",
        "FROM main.field_strategist_cockpit.initiatives\n",
        "WHERE strategist_email IS NOT NULL\n",
        "  AND LOWER(COALESCE(status, '')) = 'active'\n",
        "  AND last_activity_at IS NOT NULL\n",
        "  AND last_activity_at < DATE_SUB(current_date(), 30)\n",
        "ORDER BY last_activity_at ASC\n"
      ]
    },
    {
      "name": "ds_oneoff_without_followup",
      "displayName": "oneoff_without_followup",
      "queryLines": [
        "-- T-223: One-off engagements completed >90d ago with no subsequent\n",
        "-- engagement (Focus or one-off) OR planning session at the same account\n",
        "-- after the one-off's end date. ANY follow-up activity counts as a\n",
        "-- follow-up — the panel surfaces 'true orphans'. Completion uses end_date\n",
        "-- if set, else ASQ_Start_Date (manual orphans rarely have end_date).\n",
        "WITH oneoff AS (\n",
        "  SELECT\n",
        "    e.strategist_email,\n",
        "    e.customer,\n",
        "    e.account_id,\n",
        "    COALESCE(e.account_executive, e.ae_snapshot) AS ae,\n",
        "    e.asq_id,\n",
        "    e.engagement_title,\n",
        "    COALESCE(e.end_date, e.ASQ_Start_Date) AS completed_on\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified e\n",
        "  WHERE e.strategist_email IS NOT NULL\n",
        "    AND e.account_id IS NOT NULL\n",
        "    AND NULLIF(REGEXP_REPLACE(TRIM(COALESCE(e.engagement_type, '')), '[\\r\\n]', ''), '') = 'One-off'\n",
        "    AND NULLIF(REGEXP_REPLACE(TRIM(COALESCE(e.engagement_status, '')), '[\\r\\n]', ''), '') = 'Complete'\n",
        "    AND COALESCE(e.end_date, e.ASQ_Start_Date) IS NOT NULL\n",
        "    AND COALESCE(e.end_date, e.ASQ_Start_Date) < DATE_SUB(current_date(), 90)\n",
        "),\n",
        "followup_eng AS (\n",
        "  SELECT\n",
        "    e.strategist_email,\n",
        "    e.account_id,\n",
        "    e.ASQ_Start_Date AS followup_date,\n",
        "    COALESCE(e.asq_id, '') AS followup_id\n",
        "  FROM main.field_strategist_cockpit.v_customer_engagements_unified e\n",
        "  WHERE e.strategist_email IS NOT NULL\n",
        "    AND e.account_id IS NOT NULL\n",
        "    AND e.ASQ_Start_Date IS NOT NULL\n",
        "),\n",
        "followup_plan AS (\n",
        "  SELECT\n",
        "    p.strategist_email,\n",
        "    p.account_id,\n",
        "    p.session_date AS followup_date,\n",
        "    CONCAT('plan_', CAST(p.id AS STRING)) AS followup_id\n",
        "  FROM main.field_strategist_cockpit.focused_account_planning p\n",
        "  WHERE p.strategist_email IS NOT NULL\n",
        "    AND p.account_id IS NOT NULL\n",
        "    AND p.session_date IS NOT NULL\n",
        "),\n",
        "followups AS (\n",
        "  SELECT strategist_email, account_id, followup_date, followup_id FROM followup_eng\n",
        "  UNION ALL\n",
        "  SELECT strategist_email, account_id, followup_date, followup_id FROM followup_plan\n",
        ")\n",
        "SELECT\n",
        "  o.strategist_email,\n",
        "  o.customer,\n",
        "  o.account_id,\n",
        "  o.ae,\n",
        "  o.asq_id,\n",
        "  o.engagement_title,\n",
        "  o.completed_on,\n",
        "  DATEDIFF(current_date(), o.completed_on) AS days_since_completed\n",
        "FROM oneoff o\n",
        "LEFT ANTI JOIN followups f\n",
        "  ON f.strategist_email = o.strategist_email\n",
        " AND f.account_id = o.account_id\n",
        " AND f.followup_id <> COALESCE(o.asq_id, '')\n",
        " AND f.followup_date > o.completed_on\n",
        "ORDER BY o.completed_on DESC\n"
      ]
    }
    # --- end T-223 ---
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
        ,
        # --- T-214 windowed attribution KPI ---
        {
          "widget": {
            "name": "kpi_influenced_revenue_windowed",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_influenced_revenue_windowed",
                  "fields": [
                    {
                      "name": "sum(total_influenced_revenue_windowed)",
                      "expression": "SUM(`total_influenced_revenue_windowed`)"
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
                  "fieldName": "sum(total_influenced_revenue_windowed)",
                  "format": {
                    "type": "number-currency",
                    "currencyCode": "USD",
                    "abbreviation": "compact-long",
                    "decimalPlaces": {"type": "exact", "places": 1}
                  }
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Total influenced revenue (windowed)",
                "showDescription": True,
                "description": "$DBU in attribution window: Focus = FY..FY+1, One-off = quarter +1..+4. T-214."
              }
            }
          },
          "position": {
            "x": 0,
            "y": 24,
            "width": 6,
            "height": 3
          }
        }
        # --- end T-214 windowed attribution KPI ---
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
    ,
    # --- T-221 initiative outcomes page ---
    # Appended at the end of the pages array per coordinator conflict-avoidance
    # convention. Spec ordering is informational; coordinator may reorder pages
    # post-merge. Five panels per spec: KPI strip (5 tiles), stacked bar
    # status x fy, detail table, cross-category CXO-sponsorship panel,
    # leading-indicator stalled-initiatives tile.
    {
      "name": "p_initiative_outcomes",
      "displayName": "Initiative outcomes",
      "layout": [
        {
          "widget": {
            "name": "header_initiative_outcomes",
            "multilineTextboxSpec": {
              "lines": [
                "# Initiative outcomes\n",
                "\n",
                "Internal initiatives — Field Eng improvement projects, FEIP tickets, product-feedback campaigns. ",
                "Where the strategist's *organisational* leverage shows up. ",
                "Stalled tile uses a 30-day threshold against `last_activity_at` (latest of initiative + linked exec_meetings). ",
                "On-hold and paused are intentional pauses and do NOT count as stalled."
              ]
            }
          },
          "position": {"x": 0, "y": 0, "width": 6, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_initiatives_active",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_status",
                  "fields": [
                    {"name": "sum(active_count)", "expression": "SUM(`active_count`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(active_count)"}},
              "frame": {
                "showTitle": True,
                "title": "Active initiatives",
                "showDescription": True,
                "description": "Status = 'active'"
              }
            }
          },
          "position": {"x": 0, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_initiatives_complete",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_status",
                  "fields": [
                    {"name": "sum(complete_count)", "expression": "SUM(`complete_count`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(complete_count)"}},
              "frame": {
                "showTitle": True,
                "title": "Completed FY",
                "showDescription": True,
                "description": "Status = 'complete' (filtered by FY)"
              }
            }
          },
          "position": {"x": 1, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_initiatives_on_hold",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_status",
                  "fields": [
                    {"name": "sum(on_hold_count)", "expression": "SUM(`on_hold_count`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(on_hold_count)"}},
              "frame": {
                "showTitle": True,
                "title": "On hold",
                "showDescription": True,
                "description": "Intentional pause — not stalled"
              }
            }
          },
          "position": {"x": 2, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_initiatives_stalled",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_status",
                  "fields": [
                    {"name": "sum(stalled_count)", "expression": "SUM(`stalled_count`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "sum(stalled_count)"}},
              "frame": {
                "showTitle": True,
                "title": "Stalled",
                "showDescription": True,
                "description": "Active + no activity > 30d (configurable)"
              }
            }
          },
          "position": {"x": 3, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_initiatives_feip_tracked",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_with_links",
                  "fields": [
                    {"name": "countdistinct(feip_ticket)", "expression": "COUNT(DISTINCT `feip_ticket`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "countdistinct(feip_ticket)"}},
              "frame": {
                "showTitle": True,
                "title": "FEIP tickets tracked",
                "showDescription": True,
                "description": "Distinct non-NULL feip_ticket"
              }
            }
          },
          "position": {"x": 4, "y": 2, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "chart_initiatives_by_status_fy",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_status",
                  "fields": [
                    {"name": "fy", "expression": "`fy`"},
                    {"name": "sum(initiatives_count)", "expression": "SUM(`initiatives_count`)"},
                    {"name": "status", "expression": "`status`"}
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
                  "scale": {"type": "categorical"}
                },
                "y": {
                  "fieldName": "sum(initiatives_count)",
                  "scale": {"type": "quantitative", "stackMode": "stacked"}
                },
                "color": {
                  "fieldName": "status",
                  "scale": {"type": "categorical"},
                  "legend": {"position": "bottom"}
                }
              },
              "frame": {
                "showTitle": True,
                "title": "Initiatives by status × FY (stacked)"
              }
            }
          },
          "position": {"x": 0, "y": 4, "width": 6, "height": 5}
        },
        {
          "widget": {
            "name": "tbl_initiatives_detail",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_with_links",
                  "fields": [
                    {"name": "name", "expression": "`name`"},
                    {"name": "feip_ticket", "expression": "`feip_ticket`"},
                    {"name": "status", "expression": "`status`"},
                    {"name": "fy", "expression": "`fy`"},
                    {"name": "last_activity_at", "expression": "`last_activity_at`"},
                    {"name": "days_since_last_activity", "expression": "`days_since_last_activity`"},
                    {"name": "linked_exec_meeting_count", "expression": "`linked_exec_meeting_count`"},
                    {"name": "linked_customer_engagement_count", "expression": "`linked_customer_engagement_count`"},
                    {"name": "has_cxo_sponsorship", "expression": "`has_cxo_sponsorship`"}
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
                  {"fieldName": "name", "displayName": "Initiative", "type": "string"},
                  {
                    "fieldName": "feip_ticket",
                    "displayName": "FEIP",
                    "type": "string",
                    "displayAs": "string",
                    "booleanValues": ["—", "—"]
                  },
                  {"fieldName": "status", "displayName": "Status", "type": "string"},
                  {"fieldName": "fy", "displayName": "FY", "type": "string"},
                  {"fieldName": "last_activity_at", "displayName": "Last activity", "type": "datetime"},
                  {"fieldName": "days_since_last_activity", "displayName": "Days idle", "type": "integer"},
                  {"fieldName": "linked_exec_meeting_count", "displayName": "Exec meetings", "type": "integer"},
                  {"fieldName": "linked_customer_engagement_count", "displayName": "Linked engagements", "type": "integer"},
                  {"fieldName": "has_cxo_sponsorship", "displayName": "CXO sponsored", "type": "boolean"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Initiatives detail (sortable by Days idle for stale-ness)",
                "showDescription": True,
                "description": "NULL feip_ticket renders as '—' at the panel level. Days idle = days since latest activity (initiative or linked exec_meeting)."
              }
            }
          },
          "position": {"x": 0, "y": 9, "width": 6, "height": 7}
        },
        {
          "widget": {
            "name": "tbl_initiatives_cxo_sponsored",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_with_links",
                  "fields": [
                    {"name": "name", "expression": "`name`"},
                    {"name": "feip_ticket", "expression": "`feip_ticket`"},
                    {"name": "status", "expression": "`status`"},
                    {"name": "fy", "expression": "`fy`"},
                    {"name": "cxo_meeting_count", "expression": "`cxo_meeting_count`"},
                    {"name": "has_cxo_sponsorship", "expression": "`has_cxo_sponsorship`"}
                  ],
                  "filters": [
                    {
                      "name": "has_cxo_sponsorship_filter",
                      "expression": "`has_cxo_sponsorship` = true"
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
                  {"fieldName": "name", "displayName": "Initiative", "type": "string"},
                  {"fieldName": "feip_ticket", "displayName": "FEIP", "type": "string"},
                  {"fieldName": "status", "displayName": "Status", "type": "string"},
                  {"fieldName": "fy", "displayName": "FY", "type": "string"},
                  {"fieldName": "cxo_meeting_count", "displayName": "CXO meetings", "type": "integer"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Initiatives with CXO sponsorship",
                "showDescription": True,
                "description": "Initiatives where ≥1 linked exec_meeting has is_cxo=true (cross-category linkage via exec_meetings.initiative_id)."
              }
            }
          },
          "position": {"x": 0, "y": 16, "width": 3, "height": 6}
        },
        {
          "widget": {
            "name": "tbl_initiatives_stalled",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_initiatives_with_links",
                  "fields": [
                    {"name": "name", "expression": "`name`"},
                    {"name": "feip_ticket", "expression": "`feip_ticket`"},
                    {"name": "fy", "expression": "`fy`"},
                    {"name": "days_since_last_activity", "expression": "`days_since_last_activity`"},
                    {"name": "is_stalled", "expression": "`is_stalled`"}
                  ],
                  "filters": [
                    {
                      "name": "is_stalled_filter",
                      "expression": "`is_stalled` = true"
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
                  {"fieldName": "name", "displayName": "Initiative", "type": "string"},
                  {"fieldName": "feip_ticket", "displayName": "FEIP", "type": "string"},
                  {"fieldName": "fy", "displayName": "FY", "type": "string"},
                  {"fieldName": "days_since_last_activity", "displayName": "Days idle", "type": "integer"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Stalled initiatives — leading indicator",
                "showDescription": True,
                "description": "Active initiatives with no activity > 30 days. Threshold configurable — change `> 30` in `is_stalled` definition. on_hold + paused intentionally excluded."
              }
            }
          },
          "position": {"x": 3, "y": 16, "width": 3, "height": 6}
        }
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    }
    # --- end T-221 ---
    ,
    # --- T-223 portfolio readiness page ---
    # Monday-morning worklist: 5 KPI tiles at the top, 5 detail tables below.
    # Each KPI counts rows in its dataset; the matching table renders the
    # actionable detail. Banner uses now() so the strategist knows when the
    # cache was last refreshed.
    {
      "name": "p_portfolio_readiness",
      "displayName": "Portfolio readiness",
      "layout": [
        {
          "widget": {
            "name": "header_portfolio_readiness",
            "multilineTextboxSpec": {
              "lines": [
                "# Portfolio readiness — Monday morning worklist\n",
                "\n",
                "Leading indicators across the portfolio. Each tile is a count of items that need attention; click through to the detail table below. ",
                "If anything is in red, it's drift — Focus account with no plan, Open ASQ with no next steps, stalled initiative, one-off without follow-up.\n",
                "\n",
                "_Five tiles. Five tables. Two minutes._"
              ]
            }
          },
          "position": {"x": 0, "y": 0, "width": 6, "height": 2}
        },
        {
          "widget": {
            "name": "header_last_refreshed",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_portfolio",
                  "fields": [
                    {"name": "now()", "expression": "NOW()"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "now()"}},
              "frame": {
                "showTitle": True,
                "title": "Last refreshed",
                "showDescription": True,
                "description": "Dashboard cache refresh timestamp"
              }
            }
          },
          "position": {"x": 0, "y": 2, "width": 6, "height": 1}
        },
        {
          "widget": {
            "name": "kpi_focus_without_plan",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_without_plan",
                  "fields": [
                    {"name": "count(*)", "expression": "COUNT(`account_id`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "count(*)"}},
              "frame": {
                "showTitle": True,
                "title": "Focus accounts without plan",
                "showDescription": True,
                "description": "No planning session in last 90d"
              }
            }
          },
          "position": {"x": 0, "y": 3, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_focus_without_engagement",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_without_engagement",
                  "fields": [
                    {"name": "count(*)", "expression": "COUNT(`account_id`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "count(*)"}},
              "frame": {
                "showTitle": True,
                "title": "Focus without engagement",
                "showDescription": True,
                "description": "No customer_engagement this FQ"
              }
            }
          },
          "position": {"x": 1, "y": 3, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_open_asqs_no_next_steps",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_open_asqs_without_next_steps",
                  "fields": [
                    {"name": "count(*)", "expression": "COUNT(`asq_id`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "count(*)"}},
              "frame": {
                "showTitle": True,
                "title": "Open ASQs w/o next steps",
                "showDescription": True,
                "description": "Open ASQ + empty next_steps >=14d"
              }
            }
          },
          "position": {"x": 2, "y": 3, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_stalled_initiatives",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_stalled_initiatives",
                  "fields": [
                    {"name": "count(*)", "expression": "COUNT(`initiative_id`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "count(*)"}},
              "frame": {
                "showTitle": True,
                "title": "Stalled initiatives",
                "showDescription": True,
                "description": "status=active, no activity 30d+"
              }
            }
          },
          "position": {"x": 3, "y": 3, "width": 1, "height": 2}
        },
        {
          "widget": {
            "name": "kpi_oneoff_without_followup",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff_without_followup",
                  "fields": [
                    {"name": "count(*)", "expression": "COUNT(`asq_id`)"}
                  ],
                  "disaggregated": False
                }
              }
            ],
            "spec": {
              "version": 2,
              "widgetType": "counter",
              "encodings": {"value": {"fieldName": "count(*)"}},
              "frame": {
                "showTitle": True,
                "title": "One-offs without follow-up",
                "showDescription": True,
                "description": "Completed >90d ago, no follow-up"
              }
            }
          },
          "position": {"x": 4, "y": 3, "width": 2, "height": 2}
        },
        {
          "widget": {
            "name": "tbl_focus_without_plan",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_without_plan",
                  "fields": [
                    {"name": "customer", "expression": "`customer`"},
                    {"name": "account_id", "expression": "`account_id`"},
                    {"name": "ae", "expression": "`ae`"},
                    {"name": "last_engagement_date", "expression": "`last_engagement_date`"},
                    {"name": "days_since_last_plan", "expression": "`days_since_last_plan`"},
                    {"name": "days_since_engagement_created", "expression": "`days_since_engagement_created`"}
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
                  {"fieldName": "customer", "displayName": "Customer", "type": "string"},
                  {"fieldName": "account_id", "displayName": "Account ID", "type": "string"},
                  {"fieldName": "ae", "displayName": "AE", "type": "string"},
                  {"fieldName": "last_engagement_date", "displayName": "Last engagement", "type": "date"},
                  {"fieldName": "days_since_last_plan", "displayName": "Days since last plan", "type": "integer"},
                  {"fieldName": "days_since_engagement_created", "displayName": "Engagement age (capped 90)", "type": "integer"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Focus accounts without a planning session in the last 90 days"
              }
            }
          },
          "position": {"x": 0, "y": 5, "width": 6, "height": 6}
        },
        {
          "widget": {
            "name": "tbl_focus_without_engagement",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_focus_without_engagement",
                  "fields": [
                    {"name": "customer", "expression": "`customer`"},
                    {"name": "account_id", "expression": "`account_id`"},
                    {"name": "ae", "expression": "`ae`"},
                    {"name": "last_engagement_date", "expression": "`last_engagement_date`"},
                    {"name": "days_since_last_engagement", "expression": "`days_since_last_engagement`"}
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
                  {"fieldName": "customer", "displayName": "Customer", "type": "string"},
                  {"fieldName": "account_id", "displayName": "Account ID", "type": "string"},
                  {"fieldName": "ae", "displayName": "AE", "type": "string"},
                  {"fieldName": "last_engagement_date", "displayName": "Last engagement", "type": "date"},
                  {"fieldName": "days_since_last_engagement", "displayName": "Days since last", "type": "integer"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Focus accounts with no customer_engagement this fiscal quarter"
              }
            }
          },
          "position": {"x": 0, "y": 11, "width": 6, "height": 6}
        },
        {
          "widget": {
            "name": "tbl_open_asqs_no_next_steps",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_open_asqs_without_next_steps",
                  "fields": [
                    {"name": "customer", "expression": "`customer`"},
                    {"name": "asq_id", "expression": "`asq_id`"},
                    {"name": "engagement_title", "expression": "`engagement_title`"},
                    {"name": "engagement_status", "expression": "`engagement_status`"},
                    {"name": "ae", "expression": "`ae`"},
                    {"name": "ASQ_Start_Date", "expression": "`ASQ_Start_Date`"},
                    {"name": "days_since_start", "expression": "`days_since_start`"},
                    {"name": "asq_url", "expression": "`asq_url`"}
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
                  {"fieldName": "customer", "displayName": "Customer", "type": "string"},
                  {"fieldName": "asq_id", "displayName": "ASQ", "type": "string"},
                  {"fieldName": "engagement_title", "displayName": "Title", "type": "string"},
                  {"fieldName": "engagement_status", "displayName": "Status", "type": "string"},
                  {"fieldName": "ae", "displayName": "AE", "type": "string"},
                  {"fieldName": "ASQ_Start_Date", "displayName": "Started", "type": "date"},
                  {"fieldName": "days_since_start", "displayName": "Days since start", "type": "integer"},
                  {"fieldName": "asq_url", "displayName": "Open in SFDC", "type": "string"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Open ASQs with empty next_steps for >=14 days"
              }
            }
          },
          "position": {"x": 0, "y": 17, "width": 6, "height": 6}
        },
        {
          "widget": {
            "name": "tbl_stalled_initiatives",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_stalled_initiatives",
                  "fields": [
                    {"name": "name", "expression": "`name`"},
                    {"name": "status", "expression": "`status`"},
                    {"name": "fy", "expression": "`fy`"},
                    {"name": "feip_ticket", "expression": "`feip_ticket`"},
                    {"name": "last_activity_at", "expression": "`last_activity_at`"},
                    {"name": "days_since_last_activity", "expression": "`days_since_last_activity`"},
                    {"name": "next_steps", "expression": "`next_steps`"}
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
                  {"fieldName": "name", "displayName": "Initiative", "type": "string"},
                  {"fieldName": "status", "displayName": "Status", "type": "string"},
                  {"fieldName": "fy", "displayName": "FY", "type": "string"},
                  {"fieldName": "feip_ticket", "displayName": "FEIP", "type": "string"},
                  {"fieldName": "last_activity_at", "displayName": "Last activity", "type": "datetime"},
                  {"fieldName": "days_since_last_activity", "displayName": "Days since", "type": "integer"},
                  {"fieldName": "next_steps", "displayName": "Next steps", "type": "string"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "Active initiatives with no activity for 30+ days"
              }
            }
          },
          "position": {"x": 0, "y": 23, "width": 6, "height": 6}
        },
        {
          "widget": {
            "name": "tbl_oneoff_without_followup",
            "queries": [
              {
                "name": "main_query",
                "query": {
                  "datasetName": "ds_oneoff_without_followup",
                  "fields": [
                    {"name": "customer", "expression": "`customer`"},
                    {"name": "account_id", "expression": "`account_id`"},
                    {"name": "asq_id", "expression": "`asq_id`"},
                    {"name": "engagement_title", "expression": "`engagement_title`"},
                    {"name": "ae", "expression": "`ae`"},
                    {"name": "completed_on", "expression": "`completed_on`"},
                    {"name": "days_since_completed", "expression": "`days_since_completed`"}
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
                  {"fieldName": "customer", "displayName": "Customer", "type": "string"},
                  {"fieldName": "account_id", "displayName": "Account ID", "type": "string"},
                  {"fieldName": "asq_id", "displayName": "ASQ", "type": "string"},
                  {"fieldName": "engagement_title", "displayName": "Title", "type": "string"},
                  {"fieldName": "ae", "displayName": "AE", "type": "string"},
                  {"fieldName": "completed_on", "displayName": "Completed", "type": "date"},
                  {"fieldName": "days_since_completed", "displayName": "Days since", "type": "integer"}
                ]
              },
              "frame": {
                "showTitle": True,
                "title": "One-offs completed >90d ago with no follow-up engagement or planning"
              }
            }
          },
          "position": {"x": 0, "y": 29, "width": 6, "height": 6}
        }
      ],
      "pageType": "PAGE_TYPE_CANVAS"
    }
    # --- end T-223 ---
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
