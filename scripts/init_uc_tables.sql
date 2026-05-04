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

-- Orphan engagements: the app's writeable canonical store for engagements
-- that don't have a Salesforce ASQ ID (or pre-date one). v_engagements
-- UNIONs this with asq_uco for the unified read surface.
CREATE TABLE IF NOT EXISTS engagements_manual (
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

-- App-private overlay: per-engagement annotations the strategist owns
-- (next steps, related documents). Joined onto v_engagements_unified at
-- read time. Tenancy enforced by `strategist_email`.
CREATE TABLE IF NOT EXISTS engagement_app_data (
  engagement_key  STRING NOT NULL,        -- composite key: asq_id OR "manual:{id}"
  strategist_email STRING NOT NULL,
  next_steps      STRING,
  related_documents STRING,
  updated_at      TIMESTAMP,
  CONSTRAINT pk_engagement_app_data PRIMARY KEY (engagement_key, strategist_email)
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
CREATE TABLE IF NOT EXISTS app_audit_log (
  ts              TIMESTAMP NOT NULL,
  user_email      STRING NOT NULL,
  action          STRING NOT NULL,
  target_type     STRING NOT NULL,
  target_id       STRING,
  result          STRING NOT NULL,
  extra           STRING                 -- JSON payload
)
USING DELTA
PARTITIONED BY (DATE(ts));
