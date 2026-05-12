-- T-215: rename `engagements_*` → `customer_engagements_*` in UC.
--
-- Run once per environment, AFTER deploying the matching repo commit.
-- The cockpit code references the new names from c8eb314 forward, so the
-- UC objects MUST be renamed before the app is restarted, or DBSQL
-- queries will fail.
--
-- Motivation: the cockpit will track three top-level engagement categories
-- (evangelism, initiatives, customer engagements). Keeping the bare name
-- "engagements_*" for the customer-engagement category alone is ambiguous
-- once T-216 lands new tables alongside.
--
-- Why DROP + ALTER + CREATE (not just ALTER ... RENAME TO):
-- ALTER VIEW ... RENAME TO renames the object but does NOT rewrite the
-- view body. v_engagements references engagements_manual, and
-- v_engagements_unified references v_engagements — after a pure rename
-- both view bodies would reference non-existent objects. So the views are
-- dropped, the base tables are renamed, and the views are recreated with
-- bodies that point at the new base names.
--
-- Re-run behaviour: the DROP VIEW IF EXISTS + CREATE OR REPLACE VIEW
-- steps are idempotent. The two ALTER TABLE statements will fail on
-- re-run (because the source name no longer exists). That's intentional:
-- a second-run failure is a loud signal that the rename has already been
-- applied, not a silent no-op.

USE CATALOG main;
USE SCHEMA field_strategist_cockpit;

-- --- 1. Drop views (dependent view first) --------------------------------
-- v_engagements_unified depends on v_engagements, so drop it first.

DROP VIEW IF EXISTS v_engagements_unified;
DROP VIEW IF EXISTS v_engagements;

-- --- 2. Rename Delta tables ----------------------------------------------

ALTER TABLE engagements_manual
  RENAME TO customer_engagements_manual;

ALTER TABLE engagement_app_data
  RENAME TO customer_engagement_app_data;

-- --- 3. Recreate views with new names + new bodies -----------------------
-- Bodies match the pre-rename definitions byte-for-byte except for the
-- two object-name substitutions:
--   engagements_manual            → customer_engagements_manual
--   v_engagements                 → v_customer_engagements
-- WITH SCHEMA COMPENSATION and all column COMMENTs are preserved.

CREATE OR REPLACE VIEW v_customer_engagements (
  strategist_email,
  account_id COMMENT 'Customer SFDC account ID',
  engagement_format COMMENT 'Parsed from k:v header in ASQ_Description; manual.engagement_format for orphans',
  engagement_type COMMENT 'One-off / Focus, parsed from k:v header for SFDC',
  engagement_status COMMENT 'New / In Progress / On Hold / Complete',
  customer COMMENT 'Account name',
  engagement_title COMMENT 'ASQ Title or manual title',
  asq_owner COMMENT 'Name of the owner responsible for the approval request [AI Generated]',
  asq_url COMMENT 'Lightning URL to the ASQ',
  asq_id COMMENT 'AR-XXXXXXX human-readable ID, NULL for orphans',
  asq_record_id COMMENT 'SFDC record GUID for joins, NULL for orphans',
  ASQ_Start_Date COMMENT 'Requested start date (SF Start_Date__c) or manual entry',
  end_date COMMENT 'SF End_Date__c, NULL for manual rows',
  description COMMENT 'Full Request_Description__c (includes k:v header), NULL for manual rows',
  fy COMMENT 'Fiscal year — k:v override wins, falls back to start_fy_year',
  quarter COMMENT 'Fiscal quarter — k:v override wins, falls back to start_fy_quarter',
  related_documents COMMENT 'tbc for SFDC (not in source); free text for manual',
  next_steps COMMENT 'Reverse-chron status notes + #TODO from SFDC ASQ_Notes or manual.next_steps',
  ae COMMENT 'AE snapshot (manual rows only); SFDC AE comes from v_customer_engagements_unified',
  source COMMENT 'sfdc | manual')
COMMENT 'Unified customer engagement view for Felix Mutzl strategist work — UNION of Salesforce ASQs and manual entries (T-215: renamed from v_engagements)'
WITH SCHEMA COMPENSATION
AS
SELECT DISTINCT
    'felix.mutzl@databricks.com' AS strategist_email,
    AccountId AS account_id,
    TRIM(regexp_extract(ASQ_Description, 'format:([^\n]+)', 1)) AS engagement_format,
    TRIM(regexp_extract(ASQ_Description, 'type:([^\n]+)', 1)) AS engagement_type,
    ASQ_Status AS engagement_status,
    Account AS customer,
    ASQ_Title AS engagement_title,
    ASQ_Owner AS asq_owner,
    CONCAT('https://databricks.lightning.force.com/lightning/r/ApprovalRequest__c/', ASQ_ID, '/view') AS asq_url,
    ASQ_Name AS asq_id,
    ASQ_ID AS asq_record_id,
    ASQ_Start_Date,
    ASQ_End_Date AS end_date,
    ASQ_Description AS description,
    COALESCE(NULLIF(SUBSTR(TRIM(regexp_extract(ASQ_Description, 'quarter:([^\n]+)', 1)), 1, 4), ''), start_fy_year) AS fy,
    COALESCE(NULLIF(TRIM(regexp_extract(ASQ_Description, 'quarter:([^\n]+)', 1)), ''), start_fy_quarter) AS quarter,
    'tbc' AS related_documents,
    ASQ_Notes AS next_steps,
    CAST(NULL AS STRING) AS ae,
    'sfdc' AS source
FROM main.field_usage_dashboard.asq_uco
WHERE ASQ_Owner LIKE '%Mutzl%'
  AND start_fy_year IN ('FY25','FY26','FY27','FY28','FY29','FY30')
  AND ASQ_Status <> 'Rejected'
UNION ALL
SELECT
    strategist_email,
    account_id,
    engagement_format,
    engagement_type,
    engagement_status,
    customer,
    engagement_title,
    CAST(NULL AS STRING) AS asq_owner,
    asq_url,
    asq_id,
    CAST(NULL AS STRING) AS asq_record_id,
    ASQ_Start_Date,
    CAST(NULL AS DATE) AS end_date,
    CAST(NULL AS STRING) AS description,
    fy,
    quarter,
    related_documents,
    next_steps,
    ae,
    'manual' AS source
FROM main.field_strategist_cockpit.customer_engagements_manual;

CREATE OR REPLACE VIEW v_customer_engagements_unified (
  strategist_email,
  account_id COMMENT 'Customer SFDC account ID',
  engagement_format COMMENT 'Parsed from k:v header in ASQ_Description; manual.engagement_format for orphans',
  engagement_type COMMENT 'One-off / Focus, parsed from k:v header for SFDC',
  engagement_status COMMENT 'New / In Progress / On Hold / Complete',
  customer COMMENT 'Account name',
  engagement_title COMMENT 'ASQ Title or manual title',
  asq_owner COMMENT 'Name of the owner responsible for the approval request [AI Generated]',
  asq_url COMMENT 'Lightning URL to the ASQ',
  asq_id COMMENT 'AR-XXXXXXX human-readable ID, NULL for orphans',
  asq_record_id COMMENT 'SFDC record GUID for joins, NULL for orphans',
  ASQ_Start_Date COMMENT 'Requested start date (SF Start_Date__c) or manual entry',
  end_date COMMENT 'SF End_Date__c, NULL for manual rows',
  description COMMENT 'Full Request_Description__c (includes k:v header), NULL for manual rows',
  fy COMMENT 'Fiscal year — k:v override wins, falls back to start_fy_year',
  quarter COMMENT 'Fiscal quarter — k:v override wins, falls back to start_fy_quarter',
  related_documents COMMENT 'tbc for SFDC (not in source); free text for manual',
  next_steps COMMENT 'Reverse-chron status notes + #TODO from SFDC ASQ_Notes or manual.next_steps',
  ae_snapshot COMMENT 'AE snapshot (manual rows only); SFDC AE comes from account_executive (joined from gtm_gold)',
  source COMMENT 'sfdc | manual',
  total_dbu_dollars,
  rev_fiscal_year,
  rev_account_name COMMENT 'Source: Salesforce Account Object, Field: Name. No transformation',
  territory_region COMMENT 'Derived from Salesforce User and User Role, represents the first level of sales subregion classification.',
  territory_area COMMENT 'Derived from Salesforce User and User Role, represents the second level of sales subregion classification.',
  territory_segment COMMENT 'Derived from Salesforce User and User Role, represents the third level of sales subregion classification.',
  account_executive COMMENT 'Source: Salesforce Account Object, Field: OwnerId joined to User object')
COMMENT 'Customer engagements + revenue + territory + current AE. Use this for analysis. AE comes from two places: ae_snapshot (point-in-time, manual rows only) and account_executive (current, joined from gtm_gold). T-215: renamed from v_engagements_unified.'
WITH SCHEMA COMPENSATION
AS
SELECT
    ed.strategist_email,
    ed.account_id,
    ed.engagement_format,
    ed.engagement_type,
    ed.engagement_status,
    ed.customer,
    ed.engagement_title,
    ed.asq_owner,
    ed.asq_url,
    ed.asq_id,
    ed.asq_record_id,
    ed.ASQ_Start_Date,
    ed.end_date,
    ed.description,
    ed.fy,
    ed.quarter,
    ed.related_documents,
    ed.next_steps,
    ed.ae AS ae_snapshot,
    ed.source,
    rev.total_dbu_dollars,
    rev.fiscal_year AS rev_fiscal_year,
    rev.account_name AS rev_account_name,
    rev.bu1 AS territory_region,
    rev.bu2 AS territory_area,
    rev.bu3 AS territory_segment,
    rev.ae AS account_executive
FROM main.field_strategist_cockpit.v_customer_engagements ed
LEFT JOIN (
    SELECT account_id, account_name, bu1, bu2, bu3,
           SUM(dbu_dollars) AS total_dbu_dollars, fiscal_year, ae
    FROM main.gtm_gold.rpt_c360_overview_unpivoted
    WHERE date_grain = 'quarterly' AND fiscal_year >= 2025
    GROUP BY account_id, account_name, bu1, bu2, bu3, fiscal_year, ae
) rev ON ed.account_id = rev.account_id
     AND CASE WHEN ed.fy = 'FY25' THEN 2025
              WHEN ed.fy = 'FY26' THEN 2026
              WHEN ed.fy = 'FY27' THEN 2027
              WHEN ed.fy = 'FY28' THEN 2028
              WHEN ed.fy = 'FY29' THEN 2029
              WHEN ed.fy = 'FY30' THEN 2030
              ELSE rev.fiscal_year
         END = rev.fiscal_year;

-- --- 4. Verify ------------------------------------------------------------
-- Run these manually after the migration to confirm the rename landed:
--
--   SHOW TABLES IN main.field_strategist_cockpit;
--   -- Expected: 6 rows, all with new names
--
--   SELECT COUNT(*) FROM main.field_strategist_cockpit.customer_engagements_manual;
--   -- Expected: same row count as engagements_manual had pre-migration
--
--   SELECT COUNT(*) FROM main.field_strategist_cockpit.v_customer_engagements;
--   -- Expected: roughly (asq_uco rows for Mutzl) + (customer_engagements_manual rows)
--
--   SELECT customer, fy, quarter FROM main.field_strategist_cockpit.v_customer_engagements_unified LIMIT 3;
--   -- Expected: 3 rows (slow if warehouse is cold — gives revenue GROUP BY time to spin up).
