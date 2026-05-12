# Deployment

## Logfood deployment artifacts

These are the two Databricks-standard documents we need to file before deploying Strategist Cockpit on Central Logfood:

| Document | Link | Status |
|---|---|---|
| App Security Review Questionnaire (SDR) | https://docs.google.com/document/d/1aTX4HNwNxyYvb_RXj_hBO2Wh_2LufryZauNOroaCdRg/edit | Draft — populated 2026-04-23; SDR ticket number to be filled in by Felix |
| Design Doc — Strategist Cockpit | https://docs.google.com/document/d/16x7TzaRJihHQjKoLNfBi3QGaFDHIB5XV261lmMye6Sk/edit | WIP — Part I/II/Appendix Decision 1+2 populated 2026-04-23 |
| Design Doc template instructions (reference only) | https://docs.google.com/document/d/1Ck0aiOgKo_dT_hvfCdYS2lL73F5ty0mFyEQvyh_i6bg/edit | n/a |

### Manual finishing touches needed in the docs

Google Docs smart chips (dropdowns) and a few link-wrapped template phrases resisted programmatic edits. Felix should click through once and:

- **SDR questionnaire**
  - Confirm the **Status** dropdown is set to `Draft` (the annotation reads `Draft ← please confirm selection`).
  - Confirm the **Deployment Model** dropdown is set to `Internal`.
  - The Authorization rows ("Feature Use case in Detail | Authorization") now carry our text annotations — confirm the dropdown values match (`OBO` / `N/A`).
  - Fill the SDR ticket number in the title and on the Review Status line when Product Security creates it.
- **Design Doc**
  - REST API sub-subsection still shows `See the API design in .` — the text has an embedded empty hyperlink that `replaceAllText` couldn't target. Full route listing is already in Part II / Architecture, so either delete the stub or paste the same content.
  - Other Reviewers table rows (team, product, etc.) are empty — add reviewers once identified.
  - Part III (Additional documents) checklist rows still have template helper text — tick/cross the rows per project scope (most will be "Not required" for an internal app).

## Source-of-truth docs

- Idea prompt / working doc: [Vibing Dev Scribble – Strategist Cockpit tab](https://docs.google.com/document/d/1dpzA3kJIRBArS92Shp8-X6Se9YbWv78ospi-aybRgOQ/edit?tab=t.9kpatqkpbwru)
- Sibling effort: [Vibing Dev Scribble – strategist-toolbox tab](https://docs.google.com/document/d/1dpzA3kJIRBArS92Shp8-X6Se9YbWv78ospi-aybRgOQ/edit?tab=t.kicru0bq4kwz)

## Deploy paths

**Target workspace:** `https://adb-2548836972759138.18.azuredatabricks.net` (Central Logfood)
**Goal end-state (target):** **Autoscaling Lakebase Postgres** as the OLTP store for app-managed state — scale-to-zero compute, branching, OLTP-grade write latency. Will replace the interim UC Delta write path as soon as Lakebase Autoscaling is GA on Central Logfood. Tracked as T-211.

**Interim data store (this deployment):** Unity Catalog Delta tables under `main.field_strategist_cockpit.*`, accessed via Databricks SQL warehouse + the `databricks-sql-connector`, scoped per-strategist via OBO. Data migration to this schema completed 2026-04-29; cockpit pivot to UC + DBSQL tracked as T-206. **This is a temporary architecture** until autoscaling Lakebase is available on Central Logfood.

```bash
# Build the SPA and deploy
cd src/ui && npm run build && cd ../..
databricks apps deploy strategist-cockpit --source-code-path .
```

Alternate path via workspace import: `./upload_to_workspace.sh` (imports folders via `databricks workspace import_dir` — kept for debugging, not the primary deploy path).

## Pre-deploy checklist (from the backlog)

Before the first logfood rollout:

- ✅ **T-101 / T-108 / T-110** CORS removed; security headers middleware live; CSRF posture documented (closed in commits 002616f / 9ff3cde).
- ✅ **T-109** Pydantic validation tightened with `Literal` enums + `HttpUrl` + `max_length`.
- ✅ **T-209** Path traversal in SPA catch-all closed.
- ✅ **T-207 / T-208** Per-user audit logging + Project DELETE ownership gating live.
- ✅ **T-210** Runtime/dev deps split + hash-pinned via `uv pip compile`.
- ✅ **T-205 / F-TM-2** OBO plumbing — `current_user_token()` dep wired; chat router constructs `WorkspaceClient(host, token=user_token)` per request. `app.yaml` declares `user_authorization` scopes (`sql`, `serving.serving-endpoints`, `dashboards.genie`). Closed in commit c697186.
- ✅ **T-206 / F-TM-1** Data layer pivot to UC + DBSQL behind `DATA_BACKEND=dbsql`. Reads from `v_engagements_unified` filtered by `strategist_email`; writes stamp it. SQLite path retained for dev/pytest. Closed in commit 4a3d06d.
- ✅ **T-201 / T-202** Lakeview dashboard at `/impact`, Genie space at `/ask`. Driven by `LAKEVIEW_DASHBOARD_ID` and `GENIE_SPACE_ID` env vars; both fall back to a "View in Databricks" card when not configured. Closed in commit cee2117.
- ⏳ **T-211** Lakebase migration — deferred until Lakebase is available on Central Logfood.

### One-time manual steps for the first prod deploy

1. **Run the UC DDL.** Execute `scripts/init_uc_tables.sql` against the workspace warehouse so `customer_engagements_manual`, `customer_engagement_app_data`, `projects`, and `app_audit_log` exist before the app boots. The app does **not** auto-create these — ops owns the DDL so the App SP doesn't need CREATE-TABLE privileges. **Existing deployments** upgrading from the pre-T-215 names (`engagements_manual` / `engagement_app_data` / `v_engagements*`) must run `scripts/migrate_t215_rename.sql` once before deploying this version — the new code references the new names only.
2. **Allowlist the App for embed.** Workspace admin → Settings → **Security & Compliance** → **External access** → **Embed dashboards**, add the App's host (e.g. `<app-name>-<workspace-id>.<region>.databricksapps.com`). Without this, the `/impact` and `/ask` iframes will be blocked by the workspace embed policy.
3. **Set `CSP_FRAME_SRC`.** Add the workspace host (e.g. `adb-2548836972759138.18.azuredatabricks.net`) so the app's own CSP allows the iframe sources. Without it, the iframes are blocked by `frame-src 'none'`.
4. **(If the YAML scopes are not honored)** Open the App in the Databricks UI and add the OBO scopes manually under **User authorization → +Add scope**: `sql`, `serving.serving-endpoints`, `dashboards.genie`. Recent versions of the Apps platform read these from `app.yaml`; older versions only support the UI.

### Post-deploy verification

- **Audit-sink observability (SDR-4682 standing advisory [A-2]).** After the first deploy, tail the App's log stream and exercise a state-changing route (e.g. create or edit one engagement). The structured `audit ...` line from `strategist_cockpit.audit` should appear on every state change. Then, to confirm WARN visibility, temporarily revoke INSERT on `main.field_strategist_cockpit.app_audit_log` for the App SP, repeat the action, and verify a `Audit Delta sink failed: ...` WARN line surfaces in the log stream. Restore the grant. Rationale: the stdout sink is the durable forensic fallback; the Delta sink is for queryability. We need warehouse-write failures to be observable so silent Delta-write loss is detectable rather than mysterious. `src/backend/main.py:12` sets `logging.basicConfig(level=logging.INFO)` so WARN passes through — this check validates the platform side captures it.
