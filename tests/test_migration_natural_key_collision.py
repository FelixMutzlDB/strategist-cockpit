"""T-217: natural-key collision detection.

Two evangelism rows with the same `(strategist_email, event_name, event_date)`
but different `title` → collision reported, MERGE skipped unless
--allow-conflict is set.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from scripts.migrate_strategist_activity_from_sheet import (
    detect_natural_key_collisions,
    migrate_tab,
)

HEADERS = [
    "Event", "Type", "Title", "Date", "Location", "FY", "Quarter",
    "Resources", "# of participants", "# of views", "Comments", "Next Steps",
]


def _colliding_rows():
    return [
        HEADERS,
        [
            "Some Conference", "Breakout", "First title",
            "6 June 2024", "Munich", "FY25", "FY25Q2", "",
            "100", "", "", "[complete]",
        ],
        [
            "Some Conference", "Breakout", "Different title",
            "6 June 2024", "Berlin", "FY25", "FY25Q2", "",
            "200", "", "", "[complete]",
        ],
        [
            "Another Event", "Workshop", "Workshop title",
            "15 June 2024", "Berlin", "FY25", "FY25Q2", "",
            "50", "", "", "[complete]",
        ],
    ]


def test_detect_natural_key_collisions_finds_duplicate_keys():
    df = pd.DataFrame(
        [
            {"strategist_email": "f@x.com", "event_name": "A", "event_date": date(2024, 6, 6), "title": "t1"},
            {"strategist_email": "f@x.com", "event_name": "A", "event_date": date(2024, 6, 6), "title": "t2"},
            {"strategist_email": "f@x.com", "event_name": "B", "event_date": date(2024, 6, 6), "title": "t3"},
        ]
    )
    collisions = detect_natural_key_collisions(df, "evangelism")
    # Two rows in the colliding set; row "B" is excluded.
    assert len(collisions) == 2
    assert set(collisions["title"]) == {"t1", "t2"}


def test_detect_returns_empty_when_no_collision():
    df = pd.DataFrame(
        [
            {"strategist_email": "f@x.com", "event_name": "A", "event_date": date(2024, 6, 6), "title": "t1"},
            {"strategist_email": "f@x.com", "event_name": "B", "event_date": date(2024, 6, 6), "title": "t2"},
        ]
    )
    assert detect_natural_key_collisions(df, "evangelism").empty


def test_collision_blocks_merge_without_allow_conflict(tmp_path: Path):
    """Without --allow-conflict, the colliding rows are stripped from the
    staged parquet and reported as soft rejects."""
    staging = tmp_path / "staging"

    with patch(
        "scripts.migrate_strategist_activity_from_sheet.upload_parquet_to_volume"
    ), patch(
        "scripts.migrate_strategist_activity_from_sheet.execute_merge"
    ) as fake_merge:
        stats = migrate_tab(
            "evangelism",
            strategist_email="test@example.com",
            staging_dir=staging,
            rejects_path=None,
            apply=False,  # dry-run; the assertion is independent of mode
            warehouse_id="071969b1ec9a91ca",
            sheet_rows=_colliding_rows(),
            auth_script="unused",
            user_project="unused",
            allow_conflict=False,
        )

    # Two of the three parsed rows collide. Stats should reflect 2 rejects.
    assert stats.rows_parsed == 3
    assert stats.rows_rejected >= 2
    assert any("collision" in n for n in stats.notes)
    assert fake_merge.call_count == 0  # dry-run never merges


def test_collision_with_allow_conflict_does_not_block(tmp_path: Path):
    """With --allow-conflict, the script keeps the rows in the staged parquet
    so the MERGE deduplicates by natural key in the warehouse."""
    staging = tmp_path / "staging"

    with patch(
        "scripts.migrate_strategist_activity_from_sheet.upload_parquet_to_volume"
    ):
        stats = migrate_tab(
            "evangelism",
            strategist_email="test@example.com",
            staging_dir=staging,
            rejects_path=None,
            apply=False,
            warehouse_id="071969b1ec9a91ca",
            sheet_rows=_colliding_rows(),
            auth_script="unused",
            user_project="unused",
            allow_conflict=True,
        )

    assert stats.rows_parsed == 3
    assert not any("collision" in n for n in stats.notes)
