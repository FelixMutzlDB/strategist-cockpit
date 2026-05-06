"""Seed the local database from engagements.csv and add default projects.

Idempotent by default: if the engagements table already has rows the seeder
leaves them alone. Pass ``--force`` to truncate and reseed.

Usage:
    python -m data.seed_database            # seed only if empty
    python -m data.seed_database --force    # truncate + reseed
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

# Allow running as a module from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.database import SessionLocal, init_db  # noqa: E402
from src.backend.models import Engagement, Project  # noqa: E402

# T-107: source CSV has both "FY25-Q1" and "FY25Q1" — normalize on read.
_QUARTER_DASH = re.compile(r"(FY\d{2})-(Q\d)", re.IGNORECASE)


def normalize_quarter(value: str | None) -> str | None:
    """Collapse 'FY25-Q1' to 'FY25Q1' while preserving comma-separated lists."""
    if value is None:
        return None
    cleaned = _QUARTER_DASH.sub(lambda m: f"{m.group(1)}{m.group(2)}", value)
    return cleaned.strip() or None


def seed_engagements(force: bool = False) -> int:
    csv_path = Path(__file__).parent / "engagements.csv"
    if not csv_path.exists():
        print(f"CSV not found at {csv_path}")
        return 0

    with SessionLocal() as db:
        existing = db.query(Engagement).count()
        if existing and not force:
            print(f"Engagements table already has {existing} rows; skipping (use --force to reseed).")
            return 0
        if force:
            db.query(Engagement).delete()
            db.commit()

        count = 0
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                customer = (row.get("Customer") or "").strip()
                if not customer:
                    continue
                eng_type = (row.get("Engagement Type") or "").strip()
                title = (row.get("Engagement Title") or "").strip()
                if not eng_type and not title:
                    continue

                db.add(
                    Engagement(
                        engagement_type=eng_type or None,
                        status=(row.get("Status") or "").strip() or None,
                        customer=customer,
                        engagement_title=title or None,
                        actionable_outcome=(row.get("Actionable Outcome") or "").strip() or None,
                        ae=(row.get("AE") or "").strip() or None,
                        asq_url=(row.get("ASQ_URL") or "").strip() or None,
                        asq_id=(row.get("ASQ_ID") or "").strip() or None,
                        timeframe=(row.get("Timeframe") or "").strip() or None,
                        fy=(row.get("FY") or "").strip() or None,
                        quarter=normalize_quarter((row.get("Quarter") or "").strip() or None),
                        related_documents=(row.get("Related documents") or "").strip() or None,
                        next_steps=(row.get("Next Steps") or "").strip() or None,
                        # F-TM-1: stamp tenant on seeded rows so the local-dev
                        # strategist sees their data through the tenant filter.
                        # Override via SEED_STRATEGIST_EMAIL for multi-strategist
                        # seed datasets.
                        strategist_email=(
                            os.environ.get("SEED_STRATEGIST_EMAIL", "felix.mutzl@databricks.com")
                            .strip()
                            .lower()
                        ),
                    )
                )
                count += 1

        db.commit()
        print(f"Seeded {count} engagements.")
        return count


DEFAULT_PROJECTS = [
    dict(
        name="Systems of Intelligence",
        description=(
            "A strategic framework for building intelligence layers on top of data "
            "platforms, covering the journey from data to decisions."
        ),
        url="https://docs.google.com/presentation/d/1TwwPtXDYQQE0lHg3cbjrCZ8JIWcXE0ViYRQMbpBtA8Y/edit?slide=id.g3c711b49b16_0_1078#slide=id.g3c711b49b16_0_1078",
        category="Presentation",
    ),
    dict(
        name="Innovation Factory",
        description=(
            "An interactive Databricks App showcasing the innovation factory "
            "methodology for rapid prototyping and use case development."
        ),
        url="https://e2-demo-field-eng.cloud.databricks.com/apps/innovation-factory?o=1444828305810485",
        category="Application",
    ),
]


def seed_projects(force: bool = False) -> int:
    with SessionLocal() as db:
        existing = db.query(Project).count()
        if existing and not force:
            print(f"Projects table already has {existing} rows; skipping (use --force to reseed).")
            return 0
        if force:
            db.query(Project).delete()
            db.commit()

        for p in DEFAULT_PROJECTS:
            db.add(Project(**p))
        db.commit()
        print(f"Seeded {len(DEFAULT_PROJECTS)} default projects.")
        return len(DEFAULT_PROJECTS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Truncate existing rows before seeding (destructive).",
    )
    args = parser.parse_args()

    print("Initializing database schema...")
    init_db()
    print("Seeding engagements..." + (" (force)" if args.force else ""))
    seed_engagements(force=args.force)
    print("Seeding projects..." + (" (force)" if args.force else ""))
    seed_projects(force=args.force)
    print("Done!")


if __name__ == "__main__":
    main()
