"""Seed the local PostgreSQL database from the engagements CSV and add default projects."""

import csv
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backend.database import engine, SessionLocal, init_db
from src.backend.models import Engagement, Project


def seed_engagements():
    """Parse engagements.csv and insert into the database."""
    csv_path = Path(__file__).parent / "engagements.csv"
    if not csv_path.exists():
        print(f"CSV not found at {csv_path}")
        return

    db = SessionLocal()
    try:
        # Clear existing
        db.query(Engagement).delete()
        db.commit()

        count = 0
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip empty rows (no customer)
                customer = row.get("Customer", "").strip()
                if not customer:
                    continue
                # Skip rows that are just account names in the AE column with no engagement type
                eng_type = row.get("Engagement Type", "").strip()
                if not eng_type and not row.get("Engagement Title", "").strip():
                    continue

                engagement = Engagement(
                    engagement_type=eng_type or None,
                    status=row.get("Status", "").strip() or None,
                    customer=customer,
                    engagement_title=row.get("Engagement Title", "").strip() or None,
                    actionable_outcome=row.get("Actionable Outcome", "").strip() or None,
                    ae=row.get("AE", "").strip() or None,
                    asq_url=row.get("ASQ_URL", "").strip() or None,
                    asq_id=row.get("ASQ_ID", "").strip() or None,
                    timeframe=row.get("Timeframe", "").strip() or None,
                    fy=row.get("FY", "").strip() or None,
                    quarter=row.get("Quarter", "").strip() or None,
                    related_documents=row.get("Related documents", "").strip() or None,
                    next_steps=row.get("Next Steps", "").strip() or None,
                )
                db.add(engagement)
                count += 1

        db.commit()
        print(f"Seeded {count} engagements.")
    finally:
        db.close()


def seed_projects():
    """Insert default project gallery items."""
    db = SessionLocal()
    try:
        db.query(Project).delete()
        db.commit()

        default_projects = [
            Project(
                name="Systems of Intelligence",
                description="A strategic framework for building intelligence layers on top of data platforms, covering the journey from data to decisions.",
                url="https://docs.google.com/presentation/d/1TwwPtXDYQQE0lHg3cbjrCZ8JIWcXE0ViYRQMbpBtA8Y/edit?slide=id.g3c711b49b16_0_1078#slide=id.g3c711b49b16_0_1078",
                category="Presentation",
            ),
            Project(
                name="Innovation Factory",
                description="An interactive Databricks App showcasing the innovation factory methodology for rapid prototyping and use case development.",
                url="https://e2-demo-field-eng.cloud.databricks.com/apps/innovation-factory?o=1444828305810485",
                category="Application",
            ),
        ]

        for project in default_projects:
            db.add(project)

        db.commit()
        print(f"Seeded {len(default_projects)} default projects.")
    finally:
        db.close()


if __name__ == "__main__":
    print("Initializing database schema...")
    init_db()
    print("Seeding engagements...")
    seed_engagements()
    print("Seeding projects...")
    seed_projects()
    print("Done!")
