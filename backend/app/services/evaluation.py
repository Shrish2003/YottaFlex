from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.services.detection import DetectionFinding
from backend.app.services.generator import GroundTruthCase


EXPECTED_FINDING_TYPES = {
    "temperature_excursion": {"threshold_excursion"},
    "physically_invalid_range": {"invalid_reading"},
    "missing_reading_interval": {"telemetry_gap"},
    "calibration_failure": {"calibration_failure"},
    "delivery_before_departure": {"lifecycle_anomaly"},
    "wrong_product_threshold": {"policy_selection_error"},
    "route_delay": {"route_delay"},
}


@dataclass(frozen=True)
class EvaluationResult:
    available: bool
    unavailable_reason: str | None
    evaluation_unit: str
    matching_rule: str
    confusion_matrix: dict[str, int] | None
    metrics: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "evaluation_unit": self.evaluation_unit,
            "matching_rule": self.matching_rule,
            "confusion_matrix": self.confusion_matrix,
            "metrics": self.metrics,
        }


def evaluate_ground_truth(
    ground_truth: list[GroundTruthCase],
    findings: tuple[DetectionFinding, ...],
) -> EvaluationResult:
    """Compare labelled cases to independent detector findings.

    Cases are matched by ground_truth.entity_ids["shipment_id"]. A positive case
    requires the finding type mapped from expected_issue_or_excursion. Only
    metrics with a non-zero, evidence-supported denominator are returned.
    """

    if not ground_truth:
        return EvaluationResult(
            available=False,
            unavailable_reason="No ground-truth cases are available for this API run",
            evaluation_unit="scenario case",
            matching_rule="shipment_id plus documented finding-type mapping",
            confusion_matrix=None,
            metrics={},
        )

    findings_by_shipment: dict[str, list[DetectionFinding]] = {}
    for finding in findings:
        findings_by_shipment.setdefault(finding.shipment_id, []).append(finding)

    tp = fp = fn = tn = 0
    gap_expected = gap_detected = 0
    policy_total = policy_correct = 0
    duration_errors: list[float] = []
    mapped_types = set().union(*EXPECTED_FINDING_TYPES.values())

    for case in ground_truth:
        shipment_id = case.entity_ids.get("shipment_id", "")
        shipment_findings = findings_by_shipment.get(shipment_id, [])
        expected_types = EXPECTED_FINDING_TYPES.get(case.expected_issue_or_excursion, set())
        expected_positive = case.expected_detector_decision != "no_excursion"
        actual_positive = any(
            finding.finding_type in expected_types for finding in shipment_findings
        )
        if expected_positive and actual_positive:
            tp += 1
        elif expected_positive:
            fn += 1
        elif any(finding.finding_type in mapped_types for finding in shipment_findings):
            fp += 1
        else:
            tn += 1

        if case.scenario_type in {"sensor_dropout", "missing_interval"}:
            gap_expected += 1
            if any(finding.finding_type == "telemetry_gap" for finding in shipment_findings):
                gap_detected += 1

        if (
            case.expected_detector_decision == "excursion_expected"
            and case.expected_policy_id is not None
        ):
            excursion_findings = [
                finding
                for finding in shipment_findings
                if finding.finding_type == "threshold_excursion"
            ]
            if excursion_findings:
                policy_total += 1
                if any(finding.policy_id == case.expected_policy_id for finding in excursion_findings):
                    policy_correct += 1
                if case.expected_duration_minutes is not None:
                    durations = [
                        finding.duration_minutes
                        for finding in excursion_findings
                        if finding.duration_minutes is not None
                    ]
                    if durations:
                        duration_errors.append(
                            min(
                                abs(duration - case.expected_duration_minutes)
                                for duration in durations
                            )
                        )

    precision_denominator = tp + fp
    recall_denominator = tp + fn
    f1_denominator = 2 * tp + fp + fn
    metrics: dict[str, Any] = {
        "precision": _ratio(tp, precision_denominator),
        "recall": _ratio(tp, recall_denominator),
        "f1": _ratio(2 * tp, f1_denominator),
        "gap_recall": _ratio(gap_detected, gap_expected),
        "policy_accuracy": _ratio(policy_correct, policy_total),
        "duration_absolute_error_minutes": (
            {
                "value": sum(duration_errors) / len(duration_errors),
                "denominator": len(duration_errors),
            }
            if duration_errors
            else {
                "value": None,
                "denominator": 0,
                "unavailable_reason": "No matched case has an expected and detected duration",
            }
        ),
    }
    return EvaluationResult(
        available=True,
        unavailable_reason=None,
        evaluation_unit="scenario case",
        matching_rule="shipment_id plus documented finding-type mapping",
        confusion_matrix={"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        metrics=metrics,
    )


def _ratio(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator == 0:
        return {
            "value": None,
            "denominator": 0,
            "unavailable_reason": "Metric denominator is zero for this dataset",
        }
    return {"value": numerator / denominator, "denominator": denominator}
