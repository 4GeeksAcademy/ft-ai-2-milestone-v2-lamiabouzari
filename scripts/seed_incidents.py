"""Seed centralized incidents from the approved TrackFlow CSV."""
from __future__ import annotations
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "services"
if str(SERVICE) not in sys.path: sys.path.insert(0, str(SERVICE))
from database import get_db
from incident_analysis import validate_incident
from models.incident import CATEGORY_MAP, CSV_BRANCH_MAP, CSV_STATUS_MAP, Incident
from tinydb import Query

CSV_PATH = ROOT / "scripts" / "incidents-trackflow.csv"
SEED_NAMESPACE = "https://trackflow.example/incidents/"

def seed() -> tuple[int, int]:
    db = get_db(); inserted = skipped = 0; reasons: dict[str, int] = {}
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        result = validate_incident(row)
        if not result.valid:
            skipped += 1
            for reason in result.reasons: reasons[reason] = reasons.get(reason, 0) + 1
            continue
        stable_id = uuid5(NAMESPACE_URL, SEED_NAMESPACE + row["incident_id"].strip())
        if db.get(Query().id == str(stable_id)):
            continue
        created = datetime.fromisoformat(row["date"].strip()).replace(tzinfo=timezone.utc)
        incident = Incident(id=stable_id, title=row["description"].strip(), description=row["description"].strip(), category=CATEGORY_MAP[row["category"].strip()], status=CSV_STATUS_MAP[row["status"].strip()], origin="customer", branch=CSV_BRANCH_MAP[row["country"].strip()], created_at=created, updated_at=created)
        db.insert(incident.model_dump(mode="json")); inserted += 1
    print(f"Seed complete: inserted={inserted}, skipped={skipped}")
    if reasons: print("Skipped reasons: " + ", ".join(f"{key}={value}" for key, value in sorted(reasons.items())))
    return inserted, skipped

if __name__ == "__main__": seed()
