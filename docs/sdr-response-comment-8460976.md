# SDR-4682 — reply to comment 8460976

> Paste-ready response to the reviewer's 2026-05-XX comment
> ([SDR-4682 comment 8460976](https://databricks.atlassian.net/browse/SDR-4682?focusedCommentId=8460976))
>
> Repo: https://github.com/felix-mutzl_data/strategist-cockpit
> HEAD at time of writing: `beb1d90`

---

Thanks for the thorough re-review and for surfacing N-6 + N-4 — the canvas leak in particular was a clean miss on the original adversarial pass. All four items on your path-to-CONDITIONAL list are now landed on `main` (HEAD `beb1d90`, 4 commits beyond the `4006727b` you reviewed). Walking each:

## 1. F-TM-1 multi-tenancy + N-6 canvas leak — closed

**Commit:** [`2ab2354`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/2ab2354) — *F-TM-1 (SQLite gap) + SDR-4682 N-6: tenant-scope engagements + canvas*

You're right that the DBSQL repo path was already filtering (commit `4a3d06d`, `src/backend/repos/engagements_repo.py`) but the SQLite path and the canvas surface weren't. Both now scope by `strategist_email`:

- **SQLite Engagement model:** new `strategist_email` column, indexed, mirroring `Project.created_by_email`. Stamped from `current_user_email()` on every write.
- **`/api/engagements` (all five verbs):** GET-list / GET-id / PUT / DELETE all carry `WHERE strategist_email == caller`. POST stamps from the auth dep, never from payload. PUT also pops `strategist_email` from the partial-update payload as defence-in-depth.
- **`/api/canvas/summary/{activity}` (N-6):** new `current_user_email` dep + same filter. Without this, an attacker could read any strategist's `customer` / `next_steps` / `actionable_outcome` by guessing canvas keywords (vision/CIO/RFP/...). The query at `src/backend/routers/canvas.py:78` is now a tenant-scoped `db.query(Engagement).filter(Engagement.strategist_email == user_email).all()`.

**Cross-tenant 404 semantics:** non-owner GET / PUT / DELETE return 404 (not 403), so existence isn't leaked — same pattern you accepted for Project DELETE under F-TM-5.

**Tests (12 new, all green):**
- `test_engagement_create_stamps_strategist_email` — POST with `strategist_email: "evil@elsewhere.com"` in the payload returns a row stamped `dev@local`. Spoof loses.
- `test_engagement_list_filters_by_strategist_email` — another tenant's row is invisible to the caller's GET-list.
- `test_engagement_get/update/delete_blocks_other_tenant` — 404 on cross-tenant id; row remains in DB after a "successful" 404 from the caller's perspective.
- `test_engagement_update_does_not_let_payload_change_strategist_email` — even on my own row, my Update payload cannot re-stamp the tenant.
- `test_canvas_summary_does_not_leak_other_tenants` — directly exercises N-6: another tenant's keyword-matching engagement does not appear in `accounts` or `recent_engagements`.
- `test_canvas_summary_includes_only_callers_engagements` — same keywords, two strategists, only one row in the response.

Seeder + fixture changes go through `data/seed_database.py` (`SEED_STRATEGIST_EMAIL` env var, default `felix.mutzl@databricks.com`) and `tests/conftest.py` (test-identity `dev@local`).

## 2. F-TM-2 OBO/App SP — closed

**Commit:** [`c697186`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/c697186) — *T-205 + F-TM-2: route Stratego chat through OBO user tokens*

This landed in our 2026-05-04 sweep, before your re-review window. Just confirming for your audit:

- New `current_user_token()` FastAPI dep at `src/backend/auth.py:62` reads `X-Forwarded-Access-Token`. 401s under `STRICT_AUTH=1`; falls back to `DATABRICKS_TOKEN` in dev with a one-shot logged warning. (Lenient sibling `current_user_token_or_empty()` at `src/backend/auth.py:98` is what the routers actually inject — same `STRICT_AUTH` 401 behavior, but returns `""` in dev when no token at all is available, so SQLite dev mode doesn't 401 every CRUD call. T-220 in our backlog tracks consolidating the two.)
- `chat.py:49` now constructs `WorkspaceClient(host=settings.databricks_host or None, token=user_token)` per request — no more empty `WorkspaceClient()` defaulting to App SP.
- `app.yaml` declares OBO scopes `[sql, serving.serving-endpoints, dashboards.genie]` under `user_authorization:`.
- `tests/test_chat.py:test_chat_uses_obo_token_when_endpoint_configured` mocks the SDK and asserts the user's forwarded token reaches the `WorkspaceClient` constructor verbatim.

## 3. F-TM-4 audit Delta sink — closed (PARTIAL → closed)

**Commits:**
- [`a11a1b4`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/a11a1b4) — created `main.field_strategist_cockpit.app_audit_log` on Central Logfood (verified: `SHOW TABLES IN main.field_strategist_cockpit` returns the table).
- [`beb1d90`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/beb1d90) — wired the write path.

`src/backend/audit.py` now has `_emit_to_delta(event, user_token)` that best-effort INSERTs to `app_audit_log` when `DATA_BACKEND=dbsql` and a user OBO token is in scope. Stdout JSON sink is unchanged — that's the durable forensic backup. Warehouse failures log at WARNING but don't propagate (audit is observability, not transactional state — we don't want a warehouse hiccup to 500 a user's CRUD request). Every state-changing route call site (engagements x6, projects x6, chat x2) now passes `user_token=user_token` through to `record_event`.

**Tests (4 new):**
- writes-to-Delta when `dbsql + token` (asserts INSERT target + every column binding).
- skips-Delta when `sqlite` (no `dbsql.execute` call).
- skips-Delta when no user token (best-effort gating).
- continues-on-failure: simulated warehouse error logs WARNING, doesn't raise.

**Caveat for your reviewer pass:** the sink uses the *user's* OBO token to write their own audit row. If the user's token is valid enough to reach the route, it's valid enough to write the audit. Failure modes (revoked token, warehouse outage) are caught and logged. If you'd prefer a separate App-SP audit path so audit writes survive even when user OBO is borked, happy to add that as a follow-up — but I think this is the lower-blast-radius shape for our current threat model.

## 4. N-4 STRICT_AUTH=1 in `app.yaml` — closed

**Commit:** [`c697186`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/c697186) — same commit as F-TM-2.

`app.yaml:17` reads:

```yaml
- name: STRICT_AUTH
  value: "1"
```

Comment in the file flags *why*: "OBO is mandatory in prod — without `STRICT_AUTH=1` the app would fall back to a local dev identity and dev `DATABRICKS_TOKEN`, defeating per-user authz."

Your suggested second hardening (assert email ends `@databricks.com`) — happy to add if you'd like; let me know. Currently `current_user_email()` lower-cases the header value but doesn't validate the domain. It would be a one-liner in `src/backend/auth.py`.

## Summary

| Item | Status | Commit |
|---|---|---|
| F-TM-1 (Engagement tenancy, SQLite + DBSQL) | ✅ closed | `2ab2354` (SQLite) + `4a3d06d` (DBSQL) |
| N-6 (canvas leak) | ✅ closed | `2ab2354` |
| F-TM-2 (chat OBO) | ✅ closed | `c697186` |
| F-TM-4 (audit Delta sink) | ✅ closed | `beb1d90` (write path) + `a11a1b4` (DDL) |
| N-4 (`STRICT_AUTH=1`) | ✅ closed | `c697186` |

**Test posture:** 112 unit tests pass, 6 integration tests skipped without warehouse credentials. Tenancy assertions explicitly cover spoof attempts and cross-tenant 404 semantics on every CRUD verb plus the canvas surface. Lint clean (`ruff check`).

## Your three open questions

Acknowledged — not gating, will follow up offline:

1. **OBO grants on the strategist Okta group** for `main.field_strategist_cockpit.*`, `main.field_usage_dashboard.asq_uco`, `main.gtm_gold.*`, warehouse `071969b1ec9a91ca`, and the Stratego serving endpoint. Looking forward to your specifics.
2. **`asq_uco` access path** — happy to route through a curated surface if that's the team's preference; right now `v_engagements_unified` UNIONs from `asq_uco` directly (existing view, not authored by us).
3. **X-Frame-Options for embed inside Databricks Apps on Central Logfood** — this is the one blocker I have on `/impact` (T-201) and `/ask` (T-202). Iframes load the workspace's `/embed/dashboardsv3/<id>` and `/embed/genie/<id>` URLs, but a workspace admin needs to allowlist the App's host under **Settings → Security → External access → Embed dashboards**. I've requested it; if you can nudge the right ProdSec / Workspace-admin contact to expedite, I'll have the embeds rendering same-day after.

## Ready for re-review

Will trigger `/security-review-assistant:resume SDR-4682` referencing commits `2ab2354`, `beb1d90` (and existing `c697186` for F-TM-2 / N-4) once you've had a chance to look. Branch `sr-e1ba916a` access requested via Opal — will review your context branch as soon as the grant lands.

Thanks again — appreciate the depth of the adversarial pass.
