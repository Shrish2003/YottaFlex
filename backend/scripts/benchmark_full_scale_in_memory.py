"""Measure full-scale generation, validation, detection, and evaluation on the 1,000-shipment dataset."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys
import time

from backend.app.services.detection import detect_dataset
from backend.app.services.evaluation import evaluate_ground_truth
from backend.app.services.generator import generate_dataset
from backend.app.services.validation import validate_dataset
from backend.scripts.verify_full_scale import build_baseline_config


def main() -> int:
    config = build_baseline_config()
    print("=" * 60)
    print("YOTTAFLEX FULL-SCALE BENCHMARK (1,000 SHIPMENTS, 2,028,036 READINGS)")
    print("=" * 60)
    print(f"Config: {config.shipment_count} shipments, {config.container_count} containers, seed={config.seed}")

    # Phase 1: Generation
    t0 = time.perf_counter()
    print("\n[Phase 1] Generating full-scale synthetic dataset...")
    dataset = generate_dataset(config)
    t_gen = time.perf_counter() - t0
    print(f"  -> Generated in {t_gen:.2f}s:")
    print(f"     Shipments:       {len(dataset.shipments):>10,d}")
    print(f"     Containers:      {len(dataset.containers):>10,d}")
    print(f"     Assignments:     {len(dataset.assignments):>10,d}")
    print(f"     Sensors:         {len(dataset.sensors):>10,d}")
    print(f"     Sensor readings: {len(dataset.readings):>10,d}")
    print(f"     Route stops:     {len(dataset.route_stops):>10,d}")
    print(f"     Custody events:  {len(dataset.custody_events):>10,d}")
    print(f"     Excursions:      {len(dataset.excursions):>10,d}")
    print(f"     Evidence links:  {len(dataset.excursion_evidence):>10,d}")
    print(f"     Corrective acts: {len(dataset.corrective_actions):>10,d}")
    print(f"     Ground truth:    {len(dataset.ground_truth):>10,d}")

    # Phase 2: Validation
    t1 = time.perf_counter()
    print("\n[Phase 2] Validating operational dataset against domain constraints...")
    val = validate_dataset(dataset)
    t_val = time.perf_counter() - t1
    print(f"  -> Validated in {t_val:.2f}s: passed={val.passed}, errors={len(val.errors)}, warnings={len(val.warnings)}")
    if not val.passed:
        print(f"     Validation errors: {val.errors[:5]}", file=sys.stderr)
        return 1

    # Phase 3: Detection
    t2 = time.perf_counter()
    print("\n[Phase 3] Running detection engine across all 2,028,036 sensor readings...")
    report = detect_dataset(dataset)
    t_det = time.perf_counter() - t2
    print(f"  -> Detection completed in {t_det:.2f}s: {len(report.findings):,d} findings generated")

    finding_counts = Counter(f.finding_type for f in report.findings)
    for ftype, count in sorted(finding_counts.items()):
        print(f"     - {ftype:28s}: {count:>8,d}")

    # Phase 4: Evaluation
    t3 = time.perf_counter()
    print("\n[Phase 4] Evaluating detector output against ground-truth labels...")
    eval_result = evaluate_ground_truth(dataset.ground_truth, report.findings)
    t_eval = time.perf_counter() - t3
    print(f"  -> Evaluation completed in {t_eval:.2f}s")

    print("\n" + "=" * 60)
    print("MEASURED EVALUATION RESULTS (INDEPENDENT DETECTOR VS GROUND TRUTH)")
    print("=" * 60)
    cm = eval_result.confusion_matrix or {}
    print(f"  Confusion Matrix:")
    print(f"    True Positives  (TP): {cm.get('tp', 0):>6d}")
    print(f"    False Positives (FP): {cm.get('fp', 0):>6d}")
    print(f"    False Negatives (FN): {cm.get('fn', 0):>6d}")
    print(f"    True Negatives  (TN): {cm.get('tn', 0):>6d}")
    total_eval = sum(cm.values())
    print(f"    Total Evaluated:      {total_eval:>6d}")

    print(f"\n  Performance Metrics:")
    for metric_name, mdata in eval_result.metrics.items():
        if isinstance(mdata, dict):
            val = mdata.get("value")
            denom = mdata.get("denominator")
            if val is not None:
                print(f"    {metric_name:32s}: {val:8.4f}  (denominator={denom})")
            else:
                print(f"    {metric_name:32s}: N/A  (reason: {mdata.get('unavailable_reason')})")

    # Scenario Breakdown
    print(f"\n  Ground-Truth Scenario Breakdown:")
    gt_scenarios = Counter(c.scenario_type for c in dataset.ground_truth)
    for sc, count in sorted(gt_scenarios.items()):
        print(f"    - {sc:28s}: {count:>5d} shipments")

    # Save summary artifact
    out_dir = Path("verification")
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "full_scale_measured_summary.json"
    summary_data = {
        "dataset_counts": {
            "shipments": len(dataset.shipments),
            "containers": len(dataset.containers),
            "assignments": len(dataset.assignments),
            "sensors": len(dataset.sensors),
            "sensor_readings": len(dataset.readings),
            "route_stops": len(dataset.route_stops),
            "custody_events": len(dataset.custody_events),
            "excursions": len(dataset.excursions),
            "ground_truth": len(dataset.ground_truth),
        },
        "timings_seconds": {
            "generation": round(t_gen, 3),
            "validation": round(t_val, 3),
            "detection": round(t_det, 3),
            "evaluation": round(t_eval, 3),
            "total_benchmark": round(t_gen + t_val + t_det + t_eval, 3),
        },
        "confusion_matrix": cm,
        "metrics": eval_result.metrics,
        "findings_by_type": dict(finding_counts),
        "scenarios": dict(gt_scenarios),
    }
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"\nSummary successfully written to {summary_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
