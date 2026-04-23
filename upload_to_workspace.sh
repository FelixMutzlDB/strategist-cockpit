#!/bin/bash
# Upload strategist-cockpit to Databricks workspace
# Run: ./upload_to_workspace.sh

BASE="/Users/felix.mutzl/Databricks Git/strategist-cockpit"
WS="/Workspace/Users/felix.mutzl@databricks.com/strategist-cockpit"

echo "=== Uploading folders ==="
databricks workspace import_dir "$BASE/src/backend" "$WS/src/backend" --overwrite
databricks workspace import_dir "$BASE/static" "$WS/static" --overwrite
databricks workspace import_dir "$BASE/data" "$WS/data" --overwrite

echo "=== Uploading files ==="
databricks workspace import "$BASE/app.yaml" "$WS/app.yaml" --format AUTO --language AUTO --overwrite
databricks workspace import "$BASE/requirements.txt" "$WS/requirements.txt" --format AUTO --language AUTO --overwrite
databricks workspace import "$BASE/pyproject.toml" "$WS/pyproject.toml" --format AUTO --language AUTO --overwrite
databricks workspace import "$BASE/src/__init__.py" "$WS/src/__init__.py" --format SOURCE --language PYTHON --overwrite
databricks workspace import "$BASE/README.md" "$WS/README.md" --format AUTO --language AUTO --overwrite

echo "=== Done ==="
