-- T-206: app-managed UC Delta tables for Strategist Cockpit.
--
-- Run once per environment (replace `main.field_strategist_cockpit` if your
-- UC namespace differs). The app NEVER auto-creates these — ops owns the DDL
-- so we don't ship CREATE-TABLE privileges to the App service principal.
--
-- Sync direction policy (see docs/architecture.md): Lakebase -> UC is the only
-- permitted direction in the goal end-state (T-211). Today the app writes
-- directly to these UC tables.

USE CATALOG main;
USE SCHEMA field_strategist_cockpit;

-- Orphan customer engagements: the app's writeable canonical store for
-- customer engagements that don't have a Salesforce ASQ ID (or pre-date
-- one). v_customer_engagements UNIONs this with asq_uco for the unified
-- read surface. Renamed from `engagements_manual` under T-215 to make
-- room for non-customer engagement categories (evangelism, initiatives).
CREATE TABLE IF NOT EXISTS customer_engagements_manual (
  id              BIGINT GENERATED ALWAYS AS IDENTITY,
  strategist_email STRING NOT NULL,
  engagement_type STRING,
  status          STRING,
  customer        STRING,
  engagement_title STRING,
  actionable_outcome STRING,
  ae              STRING,
  asq_url         STRING,
  asq_id          STRING,
  timeframe       STRING,
  fy              STRING,
  quarter         STRING,
  uco_ids         STRING,
  created_at      TIMESTAMP,
  created_by_email STRING
)
USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true);

-- App-private overlay: per-customer-engagement annotations the strategist
-- owns (next steps, related documents). Joined onto
-- v_customer_engagements_unified at read time. Tenancy enforced by
-- `strategist_email`. Renamed from `engagement_app_data` under T-215.
CREATE TABLE IF NOT EXISTS customer_engagement_app_data (
  engagement_key  STRING NOT NULL,        -- composite key: asq_id OR "manual:{id}"
  strategist_email STRING NOT NULL,
  next_steps      STRING,
  related_documents STRING,
  updated_at      TIMESTAMP,
  CONSTRAINT pk_customer_engagement_app_data PRIMARY KEY (engagement_key, strategist_email)
)
USING DELTA;

-- Project gallery: the read+write store for the Gallery page.
-- F-TM-1 row filter: list/get filtered by strategist_email; delete gated by
-- created_by_email == caller OR caller is admin (mirrors SQLite behaviour).
CREATE TABLE IF NOT EXISTS projects (
  id              BIGINT GENERATED ALWAYS AS IDENTITY,
  strategist_email STRING NOT NULL,
  name            STRING NOT NULL,
  description     STRING,
  url             STRING NOT NULL,
  thumbnail_url   STRING,
  category        STRING,
  created_at      TIMESTAMP,
  created_by_email STRING NOT NULL
)
USING DELTA;

-- Audit log: structured events from src/backend/audit.py. Today the app
-- emits stdout JSON; a follow-up will write rows directly via dbsql.
-- Volume is low (single-digit RPS at most) so we don't partition. If we
-- ever need it, add `event_date DATE GENERATED ALWAYS AS (CAST(ts AS DATE))`
-- and partition by that — Delta requires generated columns for date-from-ts
-- partitioning, not raw expressions.
CREATE TABLE IF NOT EXISTS app_audit_log (
  ts              TIMESTAMP NOT NULL,
  user_email      STRING NOT NULL,
  action          STRING NOT NULL,
  target_type     STRING NOT NULL,
  target_id       STRING,
  result          STRING NOT NULL,
  extra           STRING                 -- JSON payload
)
USING DELTA;

-- ============================================================================
-- T-216: activity tables (evangelism, initiatives, account planning, execs)
-- ----------------------------------------------------------------------------
-- Four additive tables for the three top-level engagement categories that
-- live outside ASQs, plus two enrichment dimensions:
--   - evangelism_events           (top-level "evangelism" category)
--   - initiatives                 (top-level "initiative" category)
--   - focused_account_planning    (enrichment — links to customer engagements)
--   - exec_meetings               (enrichment — links to any of the three)
-- Plus `v_engagement_categories_unified` which UNIONs the three top-level
-- categories for cross-category dashboard panels.
--
-- Tenancy: every table carries `strategist_email`; reads filter on it;
-- INSERTs stamp it from the auth dep (T-205 pattern). Same spoofing-test
-- guarantee as T-206.
--
-- App layer is NOT built here — pure DDL + view. Routers/pages land in a
-- follow-up after Mode D (T-218) has produced ~2 weeks of real data.
--
-- Grants: SELECT inherits from catalog-level grants on `main`, mirroring
-- the pattern of the existing customer_engagements_* tables (no direct
-- per-table grants — verified via UC `get_effective` on 2026-05-12).
-- ============================================================================

-- Evangelism: external talks, podcasts, workshops, roundtables. One row per
-- discrete event. `event_type` enum: Keynote|Breakout|Workshop|Podcast|
-- Moderation|Roundtable|Lightning Talk|Other. `status` enum: planned|
-- delivered|cancelled. Numeric metrics (views/participants/comments) are
-- BIGINT because the source sheet can hold 7-figure podcast view counts.
CREATE TABLE IF NOT EXISTS evangelism_events (
  id              BIGINT GENERATED ALWAYS AS IDENTITY,
  strategist_email STRING NOT NULL,
  event_name      STRING NOT NULL,
  event_type      STRING,
  title           STRING,
  event_date      DATE,
  location        STRING,
  fy              STRING,
  quarter         STRING,
  resources       STRING,
  participants    BIGINT,
  views           BIGINT,
  comments        BIGINT,
  status          STRING,
  next_steps      STRING,
  created_at      TIMESTAMP,
  updated_at      TIMESTAMP
)
USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true);

-- Initiatives: internal Field Eng improvement projects, FEIP tickets,
-- product-feedback campaigns. `status` enum: active|on_hold|paused|complete.
-- `feip_ticket` is nullable (the sheet's FEIP column is mostly empty —
-- reserved for when initiatives get formal FEIP tracking). `last_activity_at`
-- is denormalised for cheap "stalled initiative" dashboard panels.
CREATE TABLE IF NOT EXISTS initiatives (
  id              BIGINT GENERATED ALWAYS AS IDENTITY,
  strategist_email STRING NOT NULL,
  name            STRING NOT NULL,
  feip_ticket     STRING,
  actionable_outcome STRING,
  resources       STRING,
  status          STRING,
  fy              STRING,
  next_steps      STRING,
  last_activity_at TIMESTAMP,
  created_at      TIMESTAMP,
  updated_at      TIMESTAMP
)
USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true);

-- Focused account planning: enrichment dimension — Focused or Light planning
-- sessions tied to a customer (and optionally an ASQ). `planning_type` enum:
-- Focused|Light. `asq_id` is a nullable informational FK to
-- v_customer_engagements.asq_id (UC does not enforce FK constraints).
CREATE TABLE IF NOT EXISTS focused_account_planning (
  id              BIGINT GENERATED ALWAYS AS IDENTITY,
  strategist_email STRING NOT NULL,
  customer        STRING,
  account_id      STRING,
  planning_type   STRING,
  actionable_outcome STRING,
  ae              STRING,
  fy              STRING,
  quarter         STRING,
  session_date    DATE,
  related_documents STRING,
  asq_id          STRING,
  next_steps      STRING,
  created_at      TIMESTAMP,
  updated_at      TIMESTAMP
)
USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true);

-- Exec meetings: enrichment dimension — meetings with named external execs.
-- `is_cxo` from the sheet's CXO TRUE/FALSE column. All three of asq_id,
-- evangelism_id, initiative_id are nullable informational FKs; 0..3 may be
-- set simultaneously (e.g. a CXO meeting can land in a customer engagement
-- AND surface an initiative AND be triggered by an evangelism event).
CREATE TABLE IF NOT EXISTS exec_meetings (
  id              BIGINT GENERATED ALWAYS AS IDENTITY,
  strategist_email STRING NOT NULL,
  customer        STRING,
  account_id      STRING,
  exec_name       STRING,
  exec_title      STRING,
  is_cxo          BOOLEAN,
  objective       STRING,
  outcome         STRING,
  meeting_date    DATE,
  asq_id          STRING,
  evangelism_id   BIGINT,
  initiative_id   BIGINT,
  context         STRING,
  created_at      TIMESTAMP,
  updated_at      TIMESTAMP
)
USING DELTA
TBLPROPERTIES (delta.enableChangeDataFeed = true);

-- Cross-category unified view: UNION the three top-level categories so
-- dashboard panels (and the future strategist-cockpit "/engagements"
-- multi-category page) can query a single relation. Children (focused
-- account planning, exec meetings) are NOT lifted into the UNION —
-- they surface via counts joined on `(category, id)` in the dashboard.
--
-- `id` is STRING so we can UNION the BIGINT IDENTITY ids of evangelism /
-- initiative with the asq_id STRING of customer rows. `activity_date` is
-- the natural anchor per category: event_date / last_activity_at::DATE /
-- ASQ_Start_Date. `quarter` is NULL for initiatives (no quarter column in
-- the initiatives table per spec).
CREATE OR REPLACE VIEW v_engagement_categories_unified (
  category COMMENT 'evangelism | initiative | customer',
  id COMMENT 'BIGINT id (evangelism/initiative) or asq_id (customer), cast to STRING',
  strategist_email,
  activity_date COMMENT 'event_date / last_activity_at::DATE / ASQ_Start_Date',
  title COMMENT 'event title / initiative name / engagement title',
  fy,
  quarter COMMENT 'NULL for initiative rows',
  status,
  next_steps)
COMMENT 'Unified view across the three top-level engagement categories — evangelism, initiative, customer. UNION ALL of evangelism_events, initiatives, and v_customer_engagements. Children (focused_account_planning, exec_meetings) surface via counts joined on (category, id) in dashboard panels.'
AS
SELECT
    'evangelism' AS category,
    CAST(id AS STRING) AS id,
    strategist_email,
    event_date AS activity_date,
    COALESCE(title, event_name) AS title,
    fy,
    quarter,
    status,
    next_steps
FROM main.field_strategist_cockpit.evangelism_events
UNION ALL
SELECT
    'initiative' AS category,
    CAST(id AS STRING) AS id,
    strategist_email,
    CAST(last_activity_at AS DATE) AS activity_date,
    name AS title,
    fy,
    CAST(NULL AS STRING) AS quarter,
    status,
    next_steps
FROM main.field_strategist_cockpit.initiatives
UNION ALL
SELECT
    'customer' AS category,
    asq_id AS id,
    strategist_email,
    ASQ_Start_Date AS activity_date,
    engagement_title AS title,
    fy,
    quarter,
    engagement_status AS status,
    next_steps
FROM main.field_strategist_cockpit.v_customer_engagements;
