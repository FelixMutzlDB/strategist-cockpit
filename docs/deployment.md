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
**Canonical data schema:** `main.field_strategist_cockpit.*` (schema creation requested; data migration tracked as backlog item T-206)

```bash
# Build the SPA and deploy
cd src/ui && npm run build && cd ../..
databricks apps deploy strategist-cockpit --source-code-path .
```

Alternate path via workspace import: `./upload_to_workspace.sh` (imports folders via `databricks workspace import_dir` — kept for debugging, not the primary deploy path).

## Pre-deploy checklist (from the backlog)

Before the first logfood rollout, these backlog items should land and be tested:

- **T-101** Tighten CORS (SDR explicitly flagged)
- **T-108** Security response headers (CSP, X-Frame-Options, etc. — SDR flagged)
- **T-109** Tighten Pydantic validation — SDR flagged as "In progress"
- **T-110** Document CSRF posture — SDR flagged as "N/A" with rationale
- **T-205** Switch Databricks calls to OBO — SDR commitment, required for multi-user access
- **T-206** Migrate data to `main.field_strategist_cockpit` + Lakebase — SDR resource matrix depends on it
