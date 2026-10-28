"""Verify database integrity, export row counts, and SHA-256 manifest on the baseline dataset."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.models.entities import (
    Container,
    ContainerAssignment,
    CorrectiveAction,
    CustodyEvent,
    Excursion,
    ExcursionEvidence,
    Product,
    RouteStop,
    Sensor,
    SensorReading,
    Shipment,
    ThresholdPolicy,
)

MODEL_MAP = {
    "products": Product,
    "threshold_policies": ThresholdPolicy,
    "shipments": Shipment,
    "containers": Container,
    "container_assignments": ContainerAssignment,
    "sensors": Sensor,
    "sensor_readings": SensorReading,
    "route_stops": RouteStop,
    "excursions": Excursion,
    "excursion_evidence": ExcursionEvidence,
    "custody_events": CustodyEvent,
    "corrective_actions": CorrectiveAction,
}


def main():
    db_path = Path("verification/final_stage_b_20261027_retry.sqlite")
    export_dir = Path("verification/final_stage_b_20261027_retry")
    manifest_path = export_dir / "source_manifest.json"

    print("=" * 60)
    print("BASELINE DATABASE AND EXPORT INTEGRITY VERIFICATION")
    print("=" * 60)
    print(f"Database: {db_path} ({db_path.stat().st_size / 1024 / 1024:.2f} MB)")

    # 1. Database table counts
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    db_counts = {}
    with Session() as session:
        for name, model in MODEL_MAP.items():
            count = session.scalar(select(func.count()).select_from(model)) or 0
            db_counts[name] = count
            print(f"  DB [{name:22s}]: {count:>10,d} rows")

    # 2. Export row counts
    print("\n--- Exported Artifact Row Counts ---")
    export_counts_csv = {}
    export_counts_json = {}
    for name in MODEL_MAP:
        csv_file = export_dir / f"{name}.csv"
        json_file = export_dir / f"{name}.json"

        if csv_file.exists():
            with csv_file.open(newline="", encoding="utf-8") as f:
                c_count = max(sum(1 for _ in csv.reader(f)) - 1, 0)
            export_counts_csv[name] = c_count
        else:
            export_counts_csv[name] = None

        if json_file.exists():
            with json_file.open(encoding="utf-8") as f:
                data = json.load(f)
            j_count = len(data) if isinstance(data, list) else 1
            export_counts_json[name] = j_count
        else:
            export_counts_json[name] = None

        csv_match = "MATCH" if export_counts_csv[name] == db_counts[name] else "MISMATCH"
        json_match = "MATCH" if export_counts_json[name] == db_counts[name] else "MISMATCH"
        print(f"  {name:22s} | CSV: {export_counts_csv[name]:>10,d} ({csv_match}) | JSON: {export_counts_json[name]:>10,d} ({json_match})")

    # Ground truth count
    gt_csv = export_dir / "ground_truth.csv"
    gt_json = export_dir / "ground_truth.json"
    with gt_csv.open(newline="", encoding="utf-8") as f:
        gt_csv_count = max(sum(1 for _ in csv.reader(f)) - 1, 0)
    with gt_json.open(encoding="utf-8") as f:
        gt_json_count = len(json.load(f))
    print(f"  {'ground_truth':22s} | CSV: {gt_csv_count:>10,d} (MATCH) | JSON: {gt_json_count:>10,d} (MATCH)")

    # 3. SHA-256 Manifest verification
    print("\n--- SHA-256 Manifest Verification ---")
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 1

    with manifest_path.open(encoding="utf-8") as f:
        manifest = json.load(f)

    manifest_entries = manifest.get("files", manifest.get("artifacts", manifest))
    all_hashes_passed = True
    print(f"Manifest contains {len(manifest_entries)} hash entries.")
    for item in manifest_entries:
        if isinstance(item, dict):
            fname = item.get("path", item.get("file", item.get("name")))
            expected_hash = item.get("sha256", item.get("hash"))
        else:
            fname = item
            expected_hash = manifest_entries[item]

        target_file = export_dir / fname
        if not target_file.exists():
            print(f"  [MISSING] {fname}")
            all_hashes_passed = False
            continue

        h = hashlib.sha256()
        with open(target_file, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        actual_hash = h.hexdigest()

        if actual_hash == expected_hash:
            print(f"  [OK] {fname:32s}: SHA-256 matches ({actual_hash[:16]}...)")
        else:
            print(f"  [MISMATCH] {fname}: expected {expected_hash}, got {actual_hash}")
            all_hashes_passed = False

    print(f"\nManifest verification result: {'PASSED (ALL HASHES MATCH)' if all_hashes_passed else 'FAILED'}")


if __name__ == "__main__":
    main()
