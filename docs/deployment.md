# Deployment

## Logfood deployment artifacts

These are the two Databricks-standard documents we need to file before deploying Strategist Cockpit on Central Logfood:

| Document | Link | Status |
|---|---|---|
| App Security Review Questionnaire (SDR) | https://docs.google.com/document/d/1aTX4HNwNxyYvb_RXj_hBO2Wh_2LufryZauNOroaCdRg/edit | Draft — SDR ticket number to be added by Felix |
| Design Doc | https://docs.google.com/document/d/16x7TzaRJihHQjKoLNfBi3QGaFDHIB5XV261lmMye6Sk/edit | WIP |
| Design Doc template instructions (reference only) | https://docs.google.com/document/d/1Ck0aiOgKo_dT_hvfCdYS2lL73F5ty0mFyEQvyh_i6bg/edit | n/a |

## Source-of-truth docs

- Idea prompt / working doc: [Vibing Dev Scribble – Strategist Cockpit tab](https://docs.google.com/document/d/1dpzA3kJIRBArS92Shp8-X6Se9YbWv78ospi-aybRgOQ/edit?tab=t.9kpatqkpbwru)
- Sibling effort: [Vibing Dev Scribble – strategist-toolbox tab](https://docs.google.com/document/d/1dpzA3kJIRBArS92Shp8-X6Se9YbWv78ospi-aybRgOQ/edit?tab=t.kicru0bq4kwz)

## Deploy paths

**Target workspace (current dev):** `https://adb-2548836972759138.18.azuredatabricks.net`
**Target for logfood rollout:** Central Logfood (exact workspace URL TBD — see open questions in the SDR draft)

```bash
# Build the SPA and deploy
cd src/ui && npm run build && cd ../..
databricks apps deploy strategist-cockpit --source-code-path .
```

Alternate path via workspace import: `./upload_to_workspace.sh` (imports folders via `databricks workspace import_dir` — kept for debugging, not the primary deploy path).
