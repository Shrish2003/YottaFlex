from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from backend.app.core.time import duration_minutes
from backend.app.models.entities import (
    ContainerAssignment,
    Excursion,
    Sensor,
    SensorReading,
    Shipment,
    ThresholdPolicy,
)
from backend.app.models.enums import (
    ExcursionSeverity,
    ReadingQualityStatus,
    SensorStatus,
    SensorType,
)
from backend.app.services.generator import GeneratedDataset


@dataclass(frozen=True)
class DetectorConfig:
    """Configuration for deterministic telemetry evaluation."""

    sampling_interval_minutes: int = 5

    def __post_init__(self) -> None:
        if self.sampling_interval_minutes <= 0:
            raise ValueError("sampling_interval_minutes must be positive")


@dataclass(frozen=True)
class DetectionFinding:
    """An explainable detector result with stable operational references."""

    finding_id: str
    finding_type: str
    reason: str
    shipment_id: str
    sensor_id: str | None = None
    assignment_id: str | None = None
    policy_id: str | None = None
    reading_ids: tuple[str, ...] = ()
    excursion_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_minutes: int | None = None
    severity: str = "warning"
    status: str = "open"


@dataclass(frozen=True)
class DetectionReport:
    findings: tuple[DetectionFinding, ...]


def detect_dataset(
    dataset: GeneratedDataset, *, config: DetectorConfig | None = None
) -> DetectionReport:
    """Evaluate operational records without reading labels or ground truth.

    Exact policy boundaries are compliant. Missing readings are reported when
    consecutive timestamps exceed the configured sampling interval. A gap
    breaks excursion continuity; it is never treated as safe evidence.
    """

    effective_config = config or DetectorConfig(
        sampling_interval_minutes=(
            dataset.config.sampling_interval_minutes if dataset.config else 5
        )
    )
    shipments = {shipment.shipment_id: shipment for shipment in dataset.shipments}
    assignments = {assignment.assignment_id: assignment for assignment in dataset.assignments}
    sensors = {sensor.sensor_id: sensor for sensor in dataset.sensors}
    policies = list(dataset.policies)
    findings: list[DetectionFinding] = []
    excursions_by_id = {
        excursion.excursion_id: excursion for excursion in dataset.excursions
    }
    evidence_pairs: set[tuple[str, str]] = set()
    for evidence in sorted(
        dataset.excursion_evidence, key=lambda item: item.evidence_id
    ):
        pair = (evidence.excursion_id, evidence.reading_id)
        if pair in evidence_pairs:
            excursion = excursions_by_id.get(evidence.excursion_id)
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="duplicate_evidence",
                    reason="excursion evidence links the same reading more than once",
                    shipment_id=excursion.shipment_id if excursion else "",
                    sensor_id=excursion.sensor_id if excursion else None,
                    assignment_id=excursion.assignment_id if excursion else None,
                    excursion_id=evidence.excursion_id,
                    reading_ids=(evidence.reading_id,),
                )
            )
        evidence_pairs.add(pair)

    for shipment in sorted(dataset.shipments, key=lambda item: item.shipment_id):
        if (
            shipment.actual_departure is not None
            and shipment.actual_delivery is not None
            and shipment.actual_delivery < shipment.actual_departure
        ):
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="lifecycle_anomaly",
                    reason="actual delivery precedes actual departure",
                    shipment_id=shipment.shipment_id,
                )
            )
        if (
            shipment.actual_delivery is not None
            and shipment.planned_delivery is not None
            and shipment.actual_delivery - shipment.planned_delivery >= timedelta(hours=5)
        ):
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="route_delay",
                    reason="actual delivery delayed by 5 or more hours beyond planned delivery schedule",
                    shipment_id=shipment.shipment_id,
                )
            )

    policies_by_id = {policy.policy_id: policy for policy in dataset.policies}
    for excursion in sorted(dataset.excursions, key=lambda item: item.excursion_id):
        shipment = shipments.get(excursion.shipment_id)
        policy = policies_by_id.get(excursion.policy_id)
        if shipment is not None and policy is not None:
            shipment_product_id = _related_id(shipment, "product", "product_id")
            policy_product_id = _related_id(policy, "product", "product_id")
            if (
                shipment_product_id
                and policy_product_id
                and shipment_product_id != policy_product_id
            ):
                findings.append(
                    DetectionFinding(
                        finding_id="",
                        finding_type="policy_selection_error",
                        reason=f"excursion {excursion.excursion_id} references policy {policy.policy_id} for a different product",
                        shipment_id=shipment.shipment_id,
                        sensor_id=excursion.sensor_id,
                        assignment_id=excursion.assignment_id,
                        policy_id=policy.policy_id,
                        excursion_id=excursion.excursion_id,
                    )
                )

    readings_by_sensor: dict[str, list[SensorReading]] = defaultdict(list)
    for reading in dataset.readings:
        readings_by_sensor[reading.sensor_id].append(reading)

    for sensor_id in sorted(readings_by_sensor):
        sensor = sensors.get(sensor_id)
        if sensor is None:
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="invalid_attribution",
                    reason="reading references an unknown sensor",
                    shipment_id="",
                    sensor_id=sensor_id,
                    reading_ids=tuple(
                        reading.reading_id
                        for reading in sorted(
                            readings_by_sensor[sensor_id],
                            key=lambda item: (item.recorded_at, item.reading_id),
                        )
                    ),
                )
            )
            continue
        findings.extend(
            _detect_sensor(
                readings_by_sensor[sensor_id],
                sensor,
                shipments,
                assignments,
                policies,
                dataset.excursions,
                effective_config,
            )
        )

    return DetectionReport(findings=_assign_finding_ids(findings))


def _detect_sensor(
    readings: list[SensorReading],
    sensor: Sensor,
    shipments: dict[str, Shipment],
    assignments: dict[str, ContainerAssignment],
    policies: list[ThresholdPolicy],
    existing_excursions: list[Excursion],
    config: DetectorConfig,
) -> list[DetectionFinding]:
    ordered = sorted(readings, key=lambda item: (item.recorded_at, item.reading_id))
    findings: list[DetectionFinding] = []
    seen_timestamps: set[datetime] = set()
    valid_violations: list[tuple[SensorReading, ThresholdPolicy, Shipment, ContainerAssignment]] = []
    evaluated: list[
        tuple[SensorReading, ThresholdPolicy, Shipment, ContainerAssignment, bool]
    ] = []

    for reading in ordered:
        if reading.recorded_at in seen_timestamps:
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="duplicate_reading",
                    reason="sensor has multiple readings at the same timestamp",
                    shipment_id=_shipment_id_for_reading(reading, assignments),
                    sensor_id=sensor.sensor_id,
                    assignment_id=reading.assignment_id,
                    reading_ids=(reading.reading_id,),
                )
            )
            continue
        seen_timestamps.add(reading.recorded_at)
        assignment = assignments.get(reading.assignment_id)
        shipment = (
            shipments.get(_related_id(assignment, "shipment", "shipment_id"))
            if assignment is not None
            else None
        )
        if (
            assignment is None
            or shipment is None
            or reading.container_id
            != _related_id(assignment, "container", "container_id")
            or _related_id(sensor, "container", "container_id")
            != _related_id(assignment, "container", "container_id")
            or not _in_assignment(reading.recorded_at, assignment)
        ):
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="invalid_attribution",
                    reason="reading is outside or inconsistent with its assignment and sensor",
                    shipment_id=shipment.shipment_id if shipment else "",
                    sensor_id=sensor.sensor_id,
                    assignment_id=reading.assignment_id,
                    reading_ids=(reading.reading_id,),
                )
            )
            continue

        if reading.quality_status == ReadingQualityStatus.INVALID:
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="invalid_reading",
                    reason="reading quality is invalid; it is not treated as a product excursion",
                    shipment_id=shipment.shipment_id,
                    sensor_id=sensor.sensor_id,
                    assignment_id=assignment.assignment_id,
                    reading_ids=(reading.reading_id,),
                )
            )

        calibration_valid = (
            sensor.status == SensorStatus.ACTIVE
            and sensor.calibrated_at <= reading.recorded_at <= sensor.calibration_due_at
        )
        if not calibration_valid:
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="calibration_failure",
                    reason="sensor status or calibration window is invalid at reading time",
                    shipment_id=shipment.shipment_id,
                    sensor_id=sensor.sensor_id,
                    assignment_id=assignment.assignment_id,
                    reading_ids=(reading.reading_id,),
                )
            )
            continue
        if reading.quality_status != ReadingQualityStatus.VALID:
            continue

        policy_matches = [
            policy
            for policy in policies
            if _related_id(policy, "product", "product_id")
            == _related_id(shipment, "product", "product_id")
            and policy.effective_from <= reading.recorded_at
            and (policy.effective_to is None or reading.recorded_at < policy.effective_to)
        ]
        if len(policy_matches) != 1:
            findings.append(
                DetectionFinding(
                    finding_id="",
                    finding_type="policy_selection_error",
                    reason="exactly one effective policy is required for the shipment product",
                    shipment_id=shipment.shipment_id,
                    sensor_id=sensor.sensor_id,
                    assignment_id=assignment.assignment_id,
                    reading_ids=(reading.reading_id,),
                )
            )
            continue
        policy = policy_matches[0]
        if _violates_policy(reading, sensor, policy):
            valid_violations.append((reading, policy, shipment, assignment))
            evaluated.append((reading, policy, shipment, assignment, True))
        else:
            evaluated.append((reading, policy, shipment, assignment, False))

    findings.extend(
        _detect_gaps(
            ordered,
            sensor,
            assignments,
            shipments,
            config.sampling_interval_minutes,
        )
    )
    findings.extend(
        _group_violations(
            valid_violations,
            sensor,
            existing_excursions,
            config.sampling_interval_minutes,
            evaluated,
        )
    )
    return findings


def _detect_gaps(
    readings: list[SensorReading],
    sensor: Sensor,
    assignments: dict[str, ContainerAssignment],
    shipments: dict[str, Shipment],
    interval_minutes: int,
) -> list[DetectionFinding]:
    findings: list[DetectionFinding] = []
    for previous, current in zip(readings, readings[1:]):
        if previous.assignment_id != current.assignment_id:
            continue
        elapsed = duration_minutes(previous.recorded_at, current.recorded_at)
        if elapsed <= interval_minutes:
            continue
        assignment = assignments.get(previous.assignment_id)
        shipment = (
            shipments.get(_related_id(assignment, "shipment", "shipment_id"))
            if assignment
            else None
        )
        findings.append(
            DetectionFinding(
                finding_id="",
                finding_type="telemetry_gap",
                reason=(
                    f"no observation for {elapsed - interval_minutes} minutes "
                    "beyond the configured sampling interval"
                ),
                shipment_id=shipment.shipment_id if shipment else "",
                sensor_id=sensor.sensor_id,
                assignment_id=previous.assignment_id,
                reading_ids=(previous.reading_id, current.reading_id),
                started_at=previous.recorded_at,
                ended_at=current.recorded_at,
                duration_minutes=elapsed,
            )
        )
    return findings


def _group_violations(
    violations: list[tuple[SensorReading, ThresholdPolicy, Shipment, ContainerAssignment]],
    sensor: Sensor,
    existing_excursions: list[Excursion],
    interval_minutes: int,
    evaluated: list[
        tuple[SensorReading, ThresholdPolicy, Shipment, ContainerAssignment, bool]
    ],
) -> list[DetectionFinding]:
    if not violations:
        return []
    ordered = sorted(violations, key=lambda item: (item[0].recorded_at, item[0].reading_id))
    groups: list[list[tuple[SensorReading, ThresholdPolicy, Shipment, ContainerAssignment]]] = []
    current = [ordered[0]]
    for item in ordered[1:]:
        elapsed = duration_minutes(
            current[-1][0].recorded_at,
            item[0].recorded_at,
        )
        if (
            elapsed <= interval_minutes
            and item[3].assignment_id == current[-1][3].assignment_id
        ):
            current.append(item)
        else:
            groups.append(current)
            current = [item]
    groups.append(current)

    findings: list[DetectionFinding] = []
    for group in groups:
        first_reading, policy, shipment, assignment = group[0]
        last_reading = group[-1][0]
        matching = next(
            (
                excursion
                for excursion in existing_excursions
                if excursion.shipment_id == shipment.shipment_id
                and excursion.sensor_id == sensor.sensor_id
                and excursion.assignment_id == assignment.assignment_id
                and _overlaps(
                    first_reading.recorded_at,
                    last_reading.recorded_at,
                    excursion.started_at,
                    excursion.ended_at,
                )
            ),
            None,
        )
        ended_at = last_reading.recorded_at
        duration = None
        status = "open"
        severity = ExcursionSeverity.WARNING.value
        recovery = next(
            (
                observation[0]
                for observation in evaluated
                if observation[0].recorded_at > last_reading.recorded_at
                and observation[3].assignment_id == assignment.assignment_id
                and not observation[4]
                and duration_minutes(
                    last_reading.recorded_at, observation[0].recorded_at
                )
                <= interval_minutes
            ),
            None,
        )
        if recovery is not None:
            ended_at = recovery.recorded_at
            duration = duration_minutes(first_reading.recorded_at, ended_at)
            status = "under_review"
        if matching is not None and matching.ended_at is not None:
            ended_at = matching.ended_at
        if matching is not None and matching.duration_minutes is not None:
            duration = matching.duration_minutes
        if matching is not None:
            status = matching.status.value
            severity = matching.severity.value
        finding = DetectionFinding(
            finding_id="",
            finding_type="threshold_excursion",
            reason="valid reading exceeds the applicable product policy",
            shipment_id=shipment.shipment_id,
            sensor_id=sensor.sensor_id,
            assignment_id=assignment.assignment_id,
            policy_id=policy.policy_id,
            reading_ids=tuple(item[0].reading_id for item in group),
            excursion_id=matching.excursion_id if matching else None,
            started_at=first_reading.recorded_at,
            ended_at=(
                ended_at
                if recovery is not None or matching is not None
                else None
            ),
            duration_minutes=duration,
            severity=severity,
            status=status,
        )
        findings.append(finding)
    return findings


def _violates_policy(
    reading: SensorReading, sensor: Sensor, policy: ThresholdPolicy
) -> bool:
    if sensor.sensor_type == SensorType.TEMPERATURE:
        return reading.value < policy.min_temp_c or reading.value > policy.max_temp_c
    if policy.min_humidity_pct is None or policy.max_humidity_pct is None:
        return False
    return (
        reading.value < policy.min_humidity_pct
        or reading.value > policy.max_humidity_pct
    )


def _in_assignment(timestamp: datetime, assignment: ContainerAssignment) -> bool:
    return timestamp >= assignment.assigned_from and (
        assignment.assigned_to is None or timestamp < assignment.assigned_to
    )


def _shipment_id_for_reading(
    reading: SensorReading, assignments: dict[str, ContainerAssignment]
) -> str:
    assignment = assignments.get(reading.assignment_id)
    return _related_id(assignment, "shipment", "shipment_id") if assignment else ""


def _related_id(record: object | None, relationship_name: str, identifier: str) -> str | None:
    if record is None:
        return None
    value = getattr(record, identifier, None)
    if value is not None:
        return value
    relationship = getattr(record, relationship_name, None)
    return getattr(relationship, identifier, None) if relationship is not None else None


def _overlaps(
    start: datetime,
    end: datetime,
    other_start: datetime,
    other_end: datetime | None,
) -> bool:
    return other_end is None or start <= other_end and end >= other_start


def _assign_finding_ids(
    findings: list[DetectionFinding],
) -> tuple[DetectionFinding, ...]:
    ordered = sorted(
        findings,
        key=lambda item: (
            item.shipment_id,
            item.sensor_id or "",
            item.started_at or datetime.min.replace(tzinfo=timezone.utc),
            item.finding_type,
            item.reading_ids,
            item.reason,
        ),
    )
    return tuple(
        DetectionFinding(
            **{**finding.__dict__, "finding_id": f"DET-{index:06d}"}
        )
        for index, finding in enumerate(ordered, 1)
    )
