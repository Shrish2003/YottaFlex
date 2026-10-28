"""Diagnose the exact cases that mismatched in evaluation."""

import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.services.detection import detect_dataset
from backend.app.services.evaluation import evaluate_ground_truth, EXPECTED_FINDING_TYPES
from backend.app.services.generator import GroundTruthCase
from backend.app.services.monitoring import load_operational_dataset


def main():
    gt_path = Path("verification/final_stage_b_20261027_retry/ground_truth.json")
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

    engine = create_engine("sqlite:///verification/final_stage_b_20261027_retry.sqlite")
    Session = sessionmaker(bind=engine)
    with Session() as session:
        dataset = load_operational_dataset(session)

    report = detect_dataset(dataset)
    result = evaluate_ground_truth(ground_truth, report.findings)

    print("ACTUAL CONFUSION MATRIX DICT:", result.confusion_matrix)
    print("METRICS:", result.metrics)

    findings_by_shipment = {}
    for f in report.findings:
        findings_by_shipment.setdefault(f.shipment_id, []).append(f)

    print("\n--- MISMATCHED CASES ANALYSIS ---")
    mismatches = []
    mapped_types = set().union(*EXPECTED_FINDING_TYPES.values())
    for case in ground_truth:
        shipment_id = case.entity_ids.get("shipment_id", "")
        shipment_findings = findings_by_shipment.get(shipment_id, [])
        expected_types = EXPECTED_FINDING_TYPES.get(case.expected_issue_or_excursion, set())
        expected_positive = case.expected_detector_decision != "no_excursion"
        actual_positive = any(f.finding_type in expected_types for f in shipment_findings)

        if expected_positive and not actual_positive:
            mismatches.append(("FALSE_NEGATIVE", case, [f.finding_type for f in shipment_findings]))
        elif not expected_positive and any(f.finding_type in mapped_types for f in shipment_findings):
            mismatches.append(("FALSE_POSITIVE", case, [f.finding_type for f in shipment_findings]))

    print(f"Total mismatches: {len(mismatches)}")
    for kind, case, found_types in mismatches:
        print(f"[{kind}] Case {case.case_id} | Scenario: {case.scenario_type} | Expected: {case.expected_issue_or_excursion} ({case.expected_detector_decision}) | Found types: {found_types} | Entity: {case.entity_ids}")


if __name__ == "__main__":
    main()
