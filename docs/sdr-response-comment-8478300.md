# SDR-4682 — reply to comment 8478300 (round-3 re-review)

> Paste-ready response to the reviewer's round-3 re-review at HEAD `a11a1b4`
> ([SDR-4682 comment 8478300](https://databricks.atlassian.net/browse/SDR-4682?focusedCommentId=8478300))
>
> Repo: https://github.com/felix-mutzl_data/strategist-cockpit
> HEAD at time of writing: `4262a3b` (4 commits beyond your `a11a1b4` snapshot;
> 6 commits beyond if you count the round-2 closure sweep that wasn't visible
> at the snapshot time either)

---

Thanks for the round-3 re-review. **All six open findings are now closed** — two were already in `main` at your review time but missed by the snapshot diff, four are landed in this round. Walking each:

## Process note: EMU repo visibility

> *"EMU repo felix-mutzl_data/strategist-cockpit @ a66d55a not accessible from ProdSec gh auth, so reviewed against the equivalent public mirror commit"*

Confirmed and important — the public mirror (`FelixMutzlDB/strategist-cockpit`) is **frozen at `ad4c93b`** (2026-05-04). All six round-2 closures and these four round-3 fixes live only at `felix-mutzl_data/strategist-cockpit`, which your gh auth can't reach. Two ways to fix this so future reviews are accurate:

1. **Cleanest:** add ProdSec or your reviewer service-account as a read collaborator on `felix-mutzl_data/strategist-cockpit` — happy to do this if you tell me which GitHub login to invite.
2. **Mirror:** I can keep `FelixMutzlDB/strategist-cockpit` as a one-way mirror of `main` and force-push from a CI job. Less ideal because of cred management; tell me if this is preferred over (1).

In the meantime, every finding below cites the commit hash so you can spot-check at https://github.com/felix-mutzl_data/strategist-cockpit/commit/<hash> if access lands.

## Findings already closed at the time of your snapshot (your reviewer didn't see them)

### N-7 (HIGH) canvas summary leak — closed in [`2ab2354`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/2ab2354)

`src/backend/routers/canvas.py:78` no longer does `db.query(Engagement).all()` — it now goes through a `current_user_email` Dep + `.filter(Engagement.strategist_email == user_email)`. The same commit added `strategist_email` to the SQLite Engagement model (mirroring `Project.created_by_email`), stamped on writes via the auth dep, never trusted from payload.

Two new tests pin this:
- `tests/test_canvas.py:test_canvas_summary_does_not_leak_other_tenants` — another strategist's CIO/exec-keyword engagement does NOT appear in caller's `accounts` or `recent_engagements`.
- `tests/test_canvas.py:test_canvas_summary_includes_only_callers_engagements` — same keywords, two strategists, only one row in the response.

### F-TM-4 audit Delta sink — closed in [`beb1d90`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/beb1d90) (+ DDL in [`a11a1b4`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/a11a1b4))

`src/backend/audit.py` now has `_emit_to_delta(event, user_token)` that best-effort INSERTs to `main.field_strategist_cockpit.app_audit_log` when `DATA_BACKEND=dbsql` and a user OBO token is in scope. Stdout sink unchanged (durable forensic backup). Warehouse hiccups log WARNING but never propagate. Every state-changing route (engagements×6, projects×6, chat×2) passes `user_token=user_token` through.

Tests in `tests/test_audit.py`:
- `test_record_event_writes_to_delta_when_dbsql_and_token` — INSERT target + every column binding asserted.
- `test_record_event_skips_delta_when_sqlite` / `_when_no_user_token` — best-effort gating.
- `test_record_event_continues_on_delta_failure` — warehouse error logs WARNING, doesn't raise.

The DDL was applied to Logfood on 2026-05-06; verified via `SHOW TABLES IN main.field_strategist_cockpit` (`app_audit_log` row present).

## Findings closed in this round-3 sweep

### N-8 (MEDIUM) frame-ancestors / X-Frame-Options — closed in [`936ab72`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/936ab72)

`src/backend/middleware.py`:
- `X-Frame-Options: SAMEORIGIN` → `DENY`
- `frame-ancestors 'self'` → `'none'`

You're right — the cockpit is never legitimately framed by anyone, not even from the same origin. Intentionally no env-var allow-list on this; tightening it in the future would require a code change rather than a config flip. `tests/test_security_headers.py:test_x_frame_options` and `test_content_security_policy_present` updated to assert the stricter values.

### N-9 (MEDIUM) style-src 'unsafe-inline' — closed in [`936ab72`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/936ab72) + [`28b6bbf`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/28b6bbf)

Split the directive per CSP3:

- `style-src 'self'` (block-level — strict, no `'unsafe-inline'`)
- `style-src-attr 'unsafe-inline'` (attribute-level only)

Tailwind compiles to a static stylesheet at build time, so no `<style>` blocks are emitted at runtime. The remaining `style="..."` attribute use is one dynamic per-row chart-bar width on `/engagements` (`pages/Engagements.tsx:481`) where the value is a runtime `${pct}%` expression — not Tailwind-able. The two static iframe heights on `/impact` and `/ask` were converted from `style={{...}}` to Tailwind arbitrary classes (`h-[calc(100vh-220px)] min-h-[600px]`).

New test `test_csp_style_src_no_unsafe_inline_at_block_level` asserts the literal directive form so a regression to the old policy fails CI.

### N-10 (LOW) vestigial psycopg2-binary — closed in [`31f15ce`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/31f15ce)

Moved from `[project] dependencies` to `[project.optional-dependencies].lakebase` in `pyproject.toml`. Hash-pinned `requirements.txt` + `requirements-dev.txt` regenerated via `uv pip compile --generate-hashes`; runtime image no longer ships psycopg2. When T-211 lands (Lakebase Autoscaling GA on Central Logfood), we'll either re-add to runtime deps or `pip install .[lakebase]`.

### N-11 (LOW) `current_user_token_or_empty` regression risk — closed in [`4262a3b`](https://github.com/felix-mutzl_data/strategist-cockpit/commit/4262a3b)

You called this exactly right and it matches our own backlog item T-220. Removed `current_user_token_or_empty` entirely; chat / engagements / projects all use strict `current_user_token` (raises 401 when no header + no `DATABRICKS_TOKEN`).

`.env.example` now documents that `DATABRICKS_TOKEN` is required for local dev — any non-empty string is fine in SQLite mode (the value is never sent upstream); a real PAT scoped to the warehouse is needed for DBSQL mode. Conftest already sets a benign default for pytest.

`docs/lessons-learned.md` captures the principle so we don't repeat the mistake: *"prefer a documented setup step over a code path that loosens prod semantics, because the latter creates an invisible regression vector."*

## Summary

| Item | Reviewer's status (snapshot `a11a1b4`) | Status now (HEAD `4262a3b`) | Closing commit |
|---|---|---|---|
| N-7 (HIGH) canvas leak | open | ✅ closed | `2ab2354` |
| F-TM-4 audit Delta sink | open | ✅ closed | `beb1d90` + `a11a1b4` (DDL) |
| N-8 (MEDIUM) frame-ancestors / XFO | open | ✅ closed | `936ab72` |
| N-9 (MEDIUM) style-src | open | ✅ closed | `936ab72` + `28b6bbf` |
| N-10 (LOW) psycopg2-binary | open | ✅ closed | `31f15ce` |
| N-11 (LOW) / T-220 token deps | open | ✅ closed | `4262a3b` |

**Test posture:** 113 unit tests pass, 6 integration tests skipped without warehouse credentials. Lint clean (`ruff check`).

## Three open questions still owed by ProdSec

Acknowledged from the previous round; flagging again so they don't fall off:

1. **OBO grants** for the strategist Okta group on `main.field_strategist_cockpit.*`, `main.field_usage_dashboard.asq_uco`, `main.gtm_gold.*`, warehouse `071969b1ec9a91ca`, Stratego serving endpoint.
2. **`asq_uco` access path** — routed to `#central-logfood-support` per your 2026-05-04 follow-up; will follow up there if I haven't gotten a definitive answer by 2026-05-12.
3. **X-Frame-Options posture** for embedding Lakeview / Genie inside Databricks Apps on Central Logfood — actually our only true blocker on `/impact` (T-201) and `/ask` (T-202) shipping. The workspace embed allowlist hasn't been flipped yet; embeds will silently render blank until it is.

## Ready for re-review

Will trigger `/security-review-assistant:resume SDR-4682` with this commit list:

- `2ab2354` (N-7), `beb1d90` (F-TM-4), `936ab72` (N-8 + N-9), `28b6bbf` (N-9 UI), `31f15ce` (N-10), `4262a3b` (N-11)

Plus please let me know how you want EMU repo access set up so the next review's snapshot is the actual code.

Thanks again — happy to iterate on anything above.
