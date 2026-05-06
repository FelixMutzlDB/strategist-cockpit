# SDR-4682 Response Draft — 2026-05-04

> **Drafting context.** Reviewing the SDR doc programmatically I found
> **zero comment threads** on the document and no Security Reviewer / Champion
> assigned yet (Status field unset; Reviewer cell still reads
> `TBD — to be assigned by ProdSec`). The "(good progress, thanks!)"
> feedback you received must have come from somewhere outside the doc
> — Slack / email / a meeting. **Please paste it before sending so I can
> tailor the response to the actual asks.** This draft assumes the
> feedback is generally positive and structures the reply around (a) the
> work shipped since 2026-04-23 and (b) the gaps still visible in the SDR
> body itself.

SDR doc: https://docs.google.com/document/d/1aTX4HNwNxyYvb_RXj_hBO2Wh_2LufryZauNOroaCdRg/edit
Repo: https://github.com/felix-mutzl_data/strategist-cockpit (main)
Last commit at time of writing: `c760d62`

---

## Status update for the reviewer (paste-ready)

> Subject: SDR-4682 (strategist-cockpit) — progress update

Since the initial SDR draft on 2026-04-23 the cockpit closed the
high-leverage findings from the security review and the four open P2
features that were called out as preconditions for the logfood roll-out:

| Date | Commit | What landed | SDR/F-TM impact |
|---|---|---|---|
| 2026-04-29 | `9ff3cde` | Path traversal closed: `StaticFiles(html=True)` + `tests/test_static_traversal.py` (sentinel + `..`/`%2f`/double-slash probes) | F-TM-3 (High) — closed |
| 2026-04-29 | `87f12bf`, `e3cdbdb` | Per-user audit logging (`record_event`); `created_by_email` ownership gating on Project DELETE | F-TM-4, F-TM-5 — closed |
| 2026-04-29 | `8bda3e2` | Runtime/dev deps split + hash-pinned via `uv pip compile` | F-TM-6 — closed |
| 2026-05-04 | `c697186` | OBO routing on the chat path: `current_user_token()` reads `X-Forwarded-Access-Token`; `WorkspaceClient(host, token=user_token)` per request; `app.yaml` declares `user_authorization: [sql, serving.serving-endpoints, dashboards.genie]` and `STRICT_AUTH=1` in prod | T-205 / F-TM-2 — closed |
| 2026-05-04 | `4a3d06d` | Data layer pivot to UC + DBSQL behind `DATA_BACKEND` flag. Reads from `v_engagements_unified` filtered by `strategist_email`; writes stamp it. Caller-supplied identity beats payload (test asserts spoofing loses). DDL in `scripts/init_uc_tables.sql`. | T-206 / F-TM-1 — closed |
| 2026-05-04 | `cee2117` | Lakeview dashboard at `/impact`, Genie space at `/ask` (iframe + fallback card). CSP `frame-src` opt-in via env. | T-201 / T-202 — closed |
| 2026-05-04 | `4cfc542` | Documentation sweep — architecture, deployment, dev guide, API ref + new `docs/lessons-learned.md` | T-203 — closed |
| 2026-05-04 | `c760d62` | Post-merge smoke-test fix: dev-mode 401 fallout from the OBO dep | (dev-loop bug; no security impact) |

**Test posture.** 100 unit tests pass; 6 integration tests skipped without
warehouse credentials. Tenancy is asserted by 7 tests in
`tests/test_dbsql_repos.py` — every SELECT carries `strategist_email`
binding; INSERT stamps it from auth dep, not payload. CSP test confirms
`frame-src 'none'` is the default, opting into the workspace host only
when `CSP_FRAME_SRC` is set.

**What's not done yet (and why).**

- **T-211 — Lakebase migration.** Goal end-state for app-managed state.
  Blocked on Autoscaling Lakebase reaching GA on Central Logfood. The
  current UC + DBSQL architecture is explicitly interim — see
  `docs/architecture.md` "Goal end-state" section.
- **One-time deploy steps** — captured in `docs/deployment.md`:
  - Run `scripts/init_uc_tables.sql` to materialise
    `engagements_manual`, `engagement_app_data`, `projects`,
    `app_audit_log`. Ops owns DDL — the App SP doesn't have CREATE.
  - Workspace admin allowlist for embed (Settings → External access →
    Embed dashboards → add the App's host). **Requested 2026-05-04;
    awaiting admin action.**
  - Optional: confirm `user_authorization` scopes via the Apps UI if the
    `app.yaml` declaration isn't honored on this Apps release.

---

## SDR doc fill-ins (per visible gap in the body)

These are direct paste-ins for the gaps the SDR doc currently has. Drop
each into the cell named.

### Gap 1 — Author(s) (header table, R3)

```
Felix Mutzl <felix.mutzl@databricks.com>  (Field Engineering, Data & AI Strategist DACH)
```

### Gap 2 — Status (header table)

Set to **Draft** until ProdSec assigns a reviewer; flip to **In Security
Review** once assigned. (Today the doc still shows the legend rather
than a single value.)

### Gap 3 — Design Doc Link (header table, R7)

```
https://docs.google.com/document/d/16x7TzaRJihHQjKoLNfBi3QGaFDHIB5XV261lmMye6Sk/edit
```

(Same Design Doc that's referenced in `docs/deployment.md` "Logfood deployment artifacts".)

### Gap 4 — Deployment Model (Part I, R1C1)

```
Internal — Field Engineering only. The app deploys as a Databricks App on
Central Logfood (adb-2548836972759138.18.azuredatabricks.net) and is
reachable only by users with workspace SSO. No external exposure.
```

### Gap 5 — User's Access sub-table

For both rows (`engagement_details` and `v_engagements_unified`) the
"User's Access via App" is **identical to direct UC access**: the app
queries the warehouse with the user's OBO token (from
`X-Forwarded-Access-Token`) — there is no app SP elevation in the read
path. Evidence: `src/backend/dbsql.py:cursor()` constructs
`databricks.sql.connect(server_hostname=..., http_path=..., access_token=user_token)`
and every read in `src/backend/repos/engagements_repo.py` filters by
`strategist_email`.

Drop-in for both rows:

```
Same as direct UC access — queries are issued with the user's OBO token
(X-Forwarded-Access-Token); no service-principal elevation in the read
path. Tenancy enforced by `WHERE strategist_email = :user_email` in the
repo layer.
```

### Gap 6 — Risk: "No rate limiting on /api/*" (Part VI, R2)

```
Description:    The cockpit's FastAPI routes have no application-level
                rate limit. The app is reachable only by Databricks
                workspace users (SSO via the Apps auth proxy) and is
                expected to handle <1 RPS in normal use (single
                strategist; <10 strategists in the rollout group).
Recommendation: Rely on (a) the Databricks Apps platform's request
                handling and abuse protections, and (b) the workspace
                SSO boundary. Re-evaluate if traffic patterns change
                (broader rollout, automated callers, or chat-driven
                bursts to the KA endpoint). If app-level limiting is
                later required, slowapi (FastAPI middleware) gives us
                per-route limits with one decorator.
Risk Level:     Low (internal app, authenticated users only)
JIRA Ticket:    None — accepted risk, revisit on broader rollout
```

### Gap 7 — Replace `JIRA-123` placeholder (Part VI, R1C4)

If the egress-filtering finding has a real SECEXP ticket, drop the
number in. If not, replace `JIRA-123` with `None — platform gap, awaiting
SECEXP ticket from ProdSec`.

### Gap 8 — Permission Management (R1C2 / R2C2)

Today this still reads "Opal Group, CLgroups, Manual updates etc?"
(template helper text). Replace with:

```
Read access (UC): governed by Unity Catalog grants on
main.field_strategist_cockpit.* — managed by the Field Engineering UC
admins. The app inherits the user's UC permissions via OBO; no app-SP
elevation.

Write access (UC, app-managed tables): same OBO model. The app SP has
no UC write privileges of its own. INSERT/UPDATE/DELETE statements run
under the strategist's identity; tenancy filtering ensures a strategist
cannot mutate another strategist's rows.

App access (who can open the app): governed by Databricks Apps "User
authorization" + workspace SSO. Default policy is the
`field_strategist_cockpit_users` Okta group (request via Opal); admin
override via the ADMIN_EMAILS env var (current value:
felix.mutzl@databricks.com, marco.metting@databricks.com).
```

(Adjust the Okta-group name if `field_strategist_cockpit_users` isn't
the actual group — let me know.)

### Gap 9 — Incident Response Considerations (Part VII)

This section is reviewer-owned ("To be completed by ProdSec & Security
Champions"). Three monitoring suggestions are pre-filled (403s on
`/api/*`, Lakebase query volume, Stratego traffic spikes). No author
action — leave for the assigned reviewer.

---

## Evidence map (link the reviewer to the right code)

| SDR claim | Code/doc evidence |
|---|---|
| OBO on every Databricks call | `src/backend/auth.py:62` (`current_user_token`) and `src/backend/auth.py:98` (`current_user_token_or_empty`); `src/backend/routers/chat.py:49` (`WorkspaceClient(host, token=user_token)`); `src/backend/dbsql.py:43` (`sql.connect(... access_token=user_token)`) |
| Per-user tenancy on data reads/writes | `src/backend/repos/engagements_repo.py` and `projects_repo.py` — every SELECT has `WHERE strategist_email = %(strategist_email)s`; every INSERT stamps it. Tests: `tests/test_dbsql_repos.py` (14 tests, including a spoof-attempt test asserting payload `strategist_email` is ignored) |
| Audit logging on state changes | `src/backend/audit.py:25` (`record_event`); called from every state-changing route (engagements POST/PUT/DELETE, projects POST/DELETE, chat POST). Chat logs `prompt_length`, never content. Tests: `tests/test_audit.py` |
| CSP / X-Frame-Options / nosniff / Referrer / Permissions | `src/backend/middleware.py:51` (`SECURITY_HEADERS`) + `_build_csp()`; tests: `tests/test_security_headers.py` (9 cases) |
| Pydantic input validation (Literal enums + URL + max_length) | `src/backend/schemas.py`; tests in `tests/test_engagements.py` cover 422 paths |
| Path traversal on SPA catch-all | `src/backend/main.py:47` (`StaticFiles(directory, html=True)`); `tests/test_static_traversal.py` (sentinel + 6 probes) |
| No CORS / no self-issued cookies | `src/backend/main.py` has no `CORSMiddleware`; tests: `tests/test_security_headers.py:test_no_cors_headers` |
| Hash-pinned dependencies | `requirements.txt` + `requirements-dev.txt` generated via `uv pip compile --generate-hashes`; CI installs with `--require-hashes` |
| Sync direction policy (Lakebase → UC, never reverse) | `docs/architecture.md` "Goal end-state" + `scripts/init_uc_tables.sql` comments |

---

## Things I'd like to verify with you before sending

1. **Where did "(good progress, thanks!)" come from?** Slack thread, email,
   meeting? If you forward me the original I can adjust the response to
   answer specific questions rather than the generic gap list above.
2. **Has SDR-4682 been formally assigned to a reviewer?** If yes, copy
   them on the response. If no, the response goes to ProdSec
   (#prodsec-help?) requesting assignment.
3. **Okta / Opal group name** for app access — Gap 8 above guesses
   `field_strategist_cockpit_users`. Confirm or correct.
4. **Real SECEXP ticket** for the egress-filtering gap (Gap 7). If none
   exists yet, ProdSec usually opens it during the review cycle — happy
   to leave the placeholder until then.
