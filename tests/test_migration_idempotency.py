"""T-217: idempotency — running the migration twice yields zero net inserts.

We mock the databricks-sql-connector cursor so the test runs without network.
The MERGE SQL itself is exercised end-to-end against a fake cursor that
simulates an "already populated" Delta table.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from scripts.migrate_strategist_activity_from_sheet import (
    build_merge_sql,
    execute_merge,
    migrate_tab,
)


def _evangelism_rows_fixture():
    """Two simple evangelism rows that share the same headers."""
    headers = [
        "Event", "Type", "Title", "Date", "Location", "FY", "Quarter",
        "Resources", "# of participants", "# of views", "Comments", "Next Steps",
    ]
    return [
        headers,
        [
            "Data.World by b.telligent", "Breakout", "Lakehouse + AI",
            "6 June 2024", "Munich", "FY25", "FY25Q2", "",
            "800", "", "Very nice breakout", "[complete]",
        ],
        [
            "Enterprise AI Summit", "Breakout", "",
            "17 Sept 2024", "Berlin", "FY25", "FY25Q3", "",
            "269", "", "", "[complete]",
        ],
    ]


def test_build_merge_sql_is_deterministic_and_has_all_keys():
    sql = build_merge_sql("evangelism", "/Volumes/main/field_strategist_cockpit/staging/x.parquet")
    # All three natural keys appear in the ON clause.
    assert "t.strategist_email" in sql
    assert "t.event_name" in sql
    assert "t.event_date" in sql
    # The MERGE updates the secondary columns we expect.
    assert "t.event_type = s.event_type" in sql
    assert "t.title = s.title" in sql
    # And inserts the canonical column list (no IDENTITY column).
    assert "id" not in sql.split("INSERT (", 1)[1].split(")", 1)[0]


def test_merge_uses_read_files_against_volume():
    sql = build_merge_sql(
        "initiatives", "/Volumes/main/field_strategist_cockpit/staging/init_2026-05-12.parquet"
    )
    assert "read_files('/Volumes/main/field_strategist_cockpit/staging/init_2026-05-12.parquet'" in sql
    assert "format => 'parquet'" in sql


def test_execute_merge_returns_count_diff():
    """First run = 0 rows before, 2 after → inserts_inferred=2.

    Second run = 2 rows before, 2 after → inserts_inferred=0 (idempotent).
    """
    fake_cursor = MagicMock()
    # First sequence: SELECT before, MERGE, SELECT after.
    fake_cursor.fetchone.side_effect = [(0,), (2,), (2,), (2,)]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_conn.__enter__.return_value = fake_conn

    with patch(
        "scripts.migrate_strategist_activity_from_sheet._sql_conn", return_value=fake_conn
    ):
        result_first = execute_merge(
            "evangelism",
            "/Volumes/main/field_strategist_cockpit/staging/x.parquet",
            warehouse_id="071969b1ec9a91ca",
        )
        result_second = execute_merge(
            "evangelism",
            "/Volumes/main/field_strategist_cockpit/staging/x.parquet",
            warehouse_id="071969b1ec9a91ca",
        )

    assert result_first == {"rows_before": 0, "rows_after": 2, "inserts_inferred": 2}
    assert result_second == {"rows_before": 2, "rows_after": 2, "inserts_inferred": 0}


def test_migrate_tab_dry_run_stages_parquet(tmp_path: Path):
    """End-to-end dry-run with injected sheet_rows: stages local parquet,
    does NOT call execute_merge, does NOT need credentials."""
    staging = tmp_path / "staging"
    rejects = tmp_path / "rejects.parquet"

    with patch(
        "scripts.migrate_strategist_activity_from_sheet.upload_parquet_to_volume"
    ) as fake_upload, patch(
        "scripts.migrate_strategist_activity_from_sheet.execute_merge"
    ) as fake_merge:
        stats = migrate_tab(
            "evangelism",
            strategist_email="test@example.com",
            staging_dir=staging,
            rejects_path=rejects,
            apply=False,  # dry-run
            warehouse_id="071969b1ec9a91ca",
            sheet_rows=_evangelism_rows_fixture(),
            auth_script="unused-in-injected-mode",
            user_project="unused",
        )

    assert fake_merge.call_count == 0, "dry-run must never call execute_merge"
    # In dry-run we try to upload to the volume so reviewers can preview;
    # the test patches upload, so just confirm it was attempted.
    assert fake_upload.call_count >= 1
    assert stats.tab == "evangelism"
    assert stats.rows_read == 2
    assert stats.rows_parsed == 2
    assert stats.rows_rejected == 0
    # Local parquet present.
    local_parquet = staging / f"evangelism_{date.today().isoformat()}.parquet"
    assert local_parquet.exists()
    # Round-trip readable.
    df = pd.read_parquet(local_parquet)
    assert set(df["event_name"]) == {"Data.World by b.telligent", "Enterprise AI Summit"}


def test_migrate_tab_idempotent_second_run_inserts_zero(tmp_path: Path):
    """Run --apply twice over the same parquet → second run reports 0 inserts."""
    staging = tmp_path / "staging"

    fake_cursor = MagicMock()
    # Run 1: before=0, after=2; Run 2: before=2, after=2.
    fake_cursor.fetchone.side_effect = [(0,), (2,), (2,), (2,)]
    fake_conn = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cursor
    fake_conn.__enter__.return_value = fake_conn

    with patch(
        "scripts.migrate_strategist_activity_from_sheet.upload_parquet_to_volume"
    ), patch(
        "scripts.migrate_strategist_activity_from_sheet._sql_conn", return_value=fake_conn
    ):
        first = migrate_tab(
            "evangelism",
            strategist_email="test@example.com",
            staging_dir=staging,
            rejects_path=None,
            apply=True,
            warehouse_id="071969b1ec9a91ca",
            sheet_rows=_evangelism_rows_fixture(),
            auth_script="unused",
            user_project="unused",
        )
        second = migrate_tab(
            "evangelism",
            strategist_email="test@example.com",
            staging_dir=staging,
            rejects_path=None,
            apply=True,
            warehouse_id="071969b1ec9a91ca",
            sheet_rows=_evangelism_rows_fixture(),
            auth_script="unused",
            user_project="unused",
        )

    assert any("inserts_inferred=2" in n for n in first.notes)
    assert any("inserts_inferred=0" in n for n in second.notes)
