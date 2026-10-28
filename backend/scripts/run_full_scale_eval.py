"""Measure full-scale detection and evaluation directly on the persisted 1,000-shipment dataset."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.services.detection import detect_dataset
from backend.app.services.evaluation import evaluate_ground_truth
from backend.app.services.generator import GroundTruthCase
from backend.app.services.monitoring import load_operational_dataset


def main() -> int:
    db_path = Path("verification/final_stage_b_20261027_retry.sqlite")
    gt_path = Path("verification/final_stage_b_20261027_retry/ground_truth.json")

    if not db_path.exists():
        print(f"Error: {db_path} does not exist", file=sys.stderr)
        return 1
    if not gt_path.exists():
        print(f"Error: {gt_path} does not exist", file=sys.stderr)
        return 1

    print(f"--- Full-Scale Evaluation Benchmark ---")
    print(f"Database: {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"Ground truth: {gt_path} ({gt_path.stat().st_size / 1024:.1f} KB)")

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_raw = json.load(f)

    ground_truth = [
        GroundTruthCase(
            case_id=c["case_id"],
            entity_ids=c["entity_ids"],
            scenario_type=c["scenario_type"],
            expected_detector_decision=c["expected_detector_decision"],
            expected_issue_or_excursion=c["expected_issue_or_excursion"],
            expected_policy_id=c.get("expected_policy_id"),
            expected_duration_minutes=c.get("expected_duration_minutes"),
            rationale=c.get("rationale", ""),
        )
        for c in gt_raw
    ]
    print(f"Loaded {len(ground_truth)} ground truth cases.")

    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)

    t0 = time.perf_counter()
    print("Loading operational dataset from SQLite...")
    with Session() as session:
        dataset = load_operational_dataset(session)
    t_load = time.perf_counter() - t0
    print(f"Loaded operational dataset in {t_load:.2f}s:")
    print(f"  Shipments: {len(dataset.shipments)}")
    print(f"  Containers: {len(dataset.containers)}")
    print(f"  Assignments: {len(dataset.assignments)}")
    print(f"  Sensors: {len(dataset.sensors)}")
    print(f"  Readings: {len(dataset.readings)}")
    print(f"  Excursions: {len(dataset.excursions)}")
    print(f"  Custody Events: {len(dataset.custody_events)}")

    t1 = time.perf_counter()
    print("Running detection engine on dataset...")
    detection_report = detect_dataset(dataset)
    t_detect = time.perf_counter() - t1
    print(f"Detection completed in {t_detect:.2f}s: {len(detection_report.findings)} findings generated.")

    t2 = time.perf_counter()
    print("Evaluating detector findings against ground truth...")
    eval_result = evaluate_ground_truth(ground_truth, detection_report.findings)
    t_eval = time.perf_counter() - t2
    print(f"Evaluation completed in {t_eval:.2f}s.")

    print("\n=== MEASURED CONFUSION MATRIX ===")
    cm = eval_result.confusion_matrix
    print(f"  True Positives (TP):  {cm.get('true_positives', 0)}")
    print(f"  False Positives (FP): {cm.get('false_positives', 0)}")
    print(f"  False Negatives (FN): {cm.get('false_negatives', 0)}")
    print(f"  True Negatives (TN):  {cm.get('true_negatives', 0)}")
    total = sum(cm.values())
    print(f"  Total Ground Truth:   {total}")

    print("\n=== MEASURED EVALUATION METRICS ===")
    for metric_name, value in eval_result.metrics.items():
        if isinstance(value, float):
            print(f"  {metric_name}: {value:.6f}")
        else:
            print(f"  {metric_name}: {value}")

    # Breakdown by scenario type
    print("\n=== SCENARIO BREAKDOWN ===")
    from collections import Counter
    cases_by_scenario = Counter(c.scenario_type for c in ground_truth)
    for sc, count in sorted(cases_by_scenario.items()):
        print(f"  {sc:30s}: {count:4d} cases")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
