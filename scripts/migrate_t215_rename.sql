-- T-215: rename `engagements_*` → `customer_engagements_*` in UC.
--
-- Run once per environment, AFTER deploying the matching repo commit.
-- The cockpit code references the new names from this commit forward, so
-- the UC objects MUST be renamed before the app is restarted, or DBSQL
-- queries will fail.
--
-- Motivation: the cockpit will track three top-level engagement categories
-- (evangelism, initiatives, customer engagements). Keeping the bare name
-- "engagements_*" for the customer-engagement category alone is ambiguous
-- once T-216 lands new tables alongside.
--
-- Idempotent: each statement uses IF EXISTS so re-running is a no-op once
-- the rename has been applied.

USE CATALOG main;
USE SCHEMA field_strategist_cockpit;

-- --- Delta tables ---------------------------------------------------------

ALTER TABLE IF EXISTS engagements_manual
  RENAME TO customer_engagements_manual;

ALTER TABLE IF EXISTS engagement_app_data
  RENAME TO customer_engagement_app_data;

-- --- Views ----------------------------------------------------------------
-- Views are defined out-of-band (not in init_uc_tables.sql) — their bodies
-- depend on `asq_uco` which the cockpit doesn't own. ALTER VIEW … RENAME
-- TO works on Unity Catalog managed views.

ALTER VIEW IF EXISTS v_engagements
  RENAME TO v_customer_engagements;

ALTER VIEW IF EXISTS v_engagements_unified
  RENAME TO v_customer_engagements_unified;

-- --- Verify ---------------------------------------------------------------
-- Run these manually after the migration to confirm the rename landed and
-- the new names return data:
--
--   SHOW TABLES IN main.field_strategist_cockpit;
--   SELECT COUNT(*) FROM main.field_strategist_cockpit.v_customer_engagements_unified;
--   SELECT COUNT(*) FROM main.field_strategist_cockpit.customer_engagements_manual;
