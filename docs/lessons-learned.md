# Lessons Learned

> Living doc. Append a section per feature/migration with what worked, what bit
> us, and the design choices we want future-us to remember. Counterpart to
> `docs/tasks/todo.md` (which is forward-looking) and the commit log (which is
> the *what*, not the *why*).

## 2026-05-04 — OBO + UC/DBSQL data layer + dashboard & Genie embeds

Closed in one sweep: T-205 (OBO), T-206 + F-TM-1 (UC + DBSQL with tenancy),
T-201 (Impact dashboard embed), T-202 (Genie embed). ~1700 LOC, 3 commits.

### Design choices worth remembering

**Two data backends behind one flag.** `DATA_BACKEND=sqlite|dbsql` lets
local pytest stay sub-second offline while prod runs against UC + the
warehouse. Routers branch in two places (read + write); the rest of the
code (auth, audit, schemas, middleware) is unaware. Trying to keep ORM
parity with raw SQL would have been a net negative — instead we let the
two paths diverge where they need to and converge at the pydantic boundary.

**Repos as plain functions, not classes.** Each `*_repo.py` is a flat
module of free functions taking `user_token`, `strategist_email`, and
operation-specific args. No abstract base class, no DI container.
Felix's "no abstractions beyond what the task requires" rule paid off —
the modules are about 130 lines each and trivially testable with
`patch.object(repo.dbsql, "fetch_all", ...)`.

**Tenancy enforced at the repo, not the router.** Every `WHERE` filter on
`strategist_email` lives in the repo functions. The router's only job is
to thread `current_user_email` and `current_user_token` through. Tests
assert the binding shows up in the SQL's params dict — a single grep for
`%(strategist_email)s` proves the rule across every read.

**Caller-supplied identity beats payload identity.** `create_engagement` /
`create_project` ignore any `strategist_email` field in the request body
and use the value from `current_user_email()` instead. There's a unit test
that explicitly tries to spoof it and asserts the spoof loses. This is a
boring rule but easy to forget when adding new endpoints.

**Per-request `WorkspaceClient`, not a module-level singleton.** Each chat
call constructs `WorkspaceClient(host, token=user_token)` fresh. Slightly
more allocation overhead than pooling, but identity-correct without
any per-user caching to invalidate. For an internal cockpit at low RPS
this is the right trade.

**Embeds: iframe + fallback card, not embed SDK.** The Impact and Ask
pages call `/api/config` on mount, build the embed URL, and render a
plain `<iframe>`. When the dashboard ID is empty they show a card
explaining what env var to set. This works for missing config, missing
allowlisting (the iframe just doesn't render — same UX), and config-edit
cycles in the workspace.

### What bit us / things to know

**The Genie iframe URL pattern is in Beta and undocumented.** Docs page
(https://docs.databricks.com/aws/en/ai-bi/admin/embed) confirms the
feature exists but doesn't quote the URL format. We wrote
`/embed/genie/<id>` based on the parallel `/embed/dashboardsv3/<id>`
pattern — adjust the `Ask.tsx` URL if your workspace's release uses a
different path. The fallback card handles the wrong-URL case gracefully.

**Workspace embed allowlisting is a separate, manual step.** Even with
correct CSP frame-src and the right URL, a workspace admin must add the
App's host under **Settings → Security → External access → Embed
dashboards** before Lakeview/Genie iframes render. This is a
silent-failure mode (iframe just stays blank); document it loudly in
`docs/deployment.md` and check it first when an embed doesn't load.

**`app.yaml` `user_authorization` may not be honored on every Apps
release.** The official docs describe scopes as a UI-only setting. We
declared them in `app.yaml` *and* documented the UI fallback in
`docs/deployment.md` so a deploy can't silently end up unscoped.

**DBSQL `INSERT` doesn't return generated IDs.** Delta tables with
`GENERATED ALWAYS AS IDENTITY` won't surface the new ID through the
connector. Workaround: stamp `created_at` server-side and `SELECT ...
WHERE strategist_email = :email AND created_at = :ts ORDER BY id DESC
LIMIT 1`. Two round-trips per write, which is fine for our RPS.

**`databricks-sql-connector` paramstyle is `pyformat`, not `qmark`.** It
binds named params as `%(name)s`, not `?`. Keep an eye on this when
copying SQL between SQLAlchemy and DBSQL paths.

**SQLite tests need a benign `DATABRICKS_TOKEN` env.** When `chat.py`
gained a `current_user_token` dep, every existing chat test started 401-ing
because the dep had no header and no `DATABRICKS_TOKEN`. Setting a
sentinel in `tests/conftest.py` (`os.environ.setdefault(...)`) was a
one-line fix. The general principle: deps with strict-auth modes need a
benign default in the test fixture, with strict-auth tests using
`monkeypatch.setenv("STRICT_AUTH", "1")` to opt in.

**One-shot warning latches need resetting in tests.** The dev
`DATABRICKS_TOKEN` fallback log is gated by a module-level boolean so
prod doesn't spam logs. Test that exercises the fallback path resets the
latch (`auth_mod._DEV_TOKEN_FALLBACK_LOGGED = False`) so it can fire
during the test.

### What we didn't do (and why it's OK)

**No real warehouse integration test for DBSQL.** We mocked
`databricks.sql.connect` at every layer. Running against an actual
warehouse from CI would mean managing test creds + cleaning up rows.
The mocked tests prove the SQL we send is right; the real-warehouse
smoke test is a manual step in `docs/deployment.md`. If we add a
nightly integration job later, gate it on creds the way
`tests/test_databricks_integration.py` already does (`pytest.skip`).

**No headless browser test of the Impact/Ask iframes.** Visual rendering
of an authenticated Databricks iframe requires either Playwright + a
real session cookie or a headless workspace clone. Out of scope. We rely
on `npm run build` + manual click-through after deploy.

**No retry / circuit-breaker on the DBSQL connection.** The cockpit is
low-RPS, single-user. If the warehouse has a transient hiccup we 500;
the user retries. Building a Tenacity-style retry wrapper would be
premature.
