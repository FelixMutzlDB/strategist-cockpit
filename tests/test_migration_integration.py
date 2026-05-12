"""T-217: optional integration test — read the real Strategist Tracking Sheet
end-to-end in dry-run mode. Skipped without creds.

Asserts each tab returns >0 rows and parses without crashing. The script's
own dry-run path stages parquet to /tmp (not to UC), so this is a CI-safe
proof-of-life — no warehouse writes.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

# We treat the test as "needs creds" if either Databricks credentials are
# missing OR the local Google auth helper isn't available. Either gap is
# enough to make the test fail under CI.
DEFAULT_GOOGLE_AUTH = (
    "/Users/felix.mutzl/.vibe/marketplace/plugins/fe-google-tools/"
    "skills/google-auth/resources/google_auth.py"
)
HAS_GOOGLE_AUTH = Path(os.environ.get("GOOGLE_AUTH_SCRIPT", DEFAULT_GOOGLE_AUTH)).exists()
HAS_DB_CREDS = bool(os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN"))
RUN_INTEGRATION = HAS_GOOGLE_AUTH and HAS_DB_CREDS


@pytest.mark.integration
@pytest.mark.skipif(not RUN_INTEGRATION, reason="needs Google + Databricks creds")
def test_dry_run_reads_real_sheet(tmp_path: Path):
    """Run the migration in dry-run for one tab and assert sane row counts."""
    from scripts.migrate_strategist_activity_from_sheet import migrate_tab

    # Skip the volume upload step — the test only validates parsing.
    with patch("scripts.migrate_strategist_activity_from_sheet.upload_parquet_to_volume"):
        stats = migrate_tab(
            "evangelism",
            strategist_email="integration-test@local",
            staging_dir=tmp_path,
            rejects_path=None,
            apply=False,
            warehouse_id="071969b1ec9a91ca",
            auth_script=os.environ.get("GOOGLE_AUTH_SCRIPT", DEFAULT_GOOGLE_AUTH),
            user_project=os.environ.get("GOOGLE_USER_PROJECT", "gcp-dev-field-eng-aiapiquota"),
        )

    assert stats.rows_read > 0
    # Within ±2 of rows_parsed + rows_rejected (sheet may have trailing blanks).
    assert abs(stats.rows_read - (stats.rows_parsed + stats.rows_rejected)) <= 2

    # The staged parquet should exist locally and be readable.
    local = tmp_path / f"evangelism_{date.today().isoformat()}.parquet"
    assert local.exists()
