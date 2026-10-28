from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from backend.app.core.time import duration_minutes
from backend.app.services.generator import GeneratedDataset, SCENARIO_TYPES


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.errors


def validate_dataset(
    dataset: GeneratedDataset, *, require_scenario_coverage: bool = True
) -> ValidationReport:
    report = ValidationReport()
    collections = {
        "products": dataset.products,
        "policies": dataset.policies,
        "shipments": dataset.shipments,
        "containers": dataset.containers,
        "assignments": dataset.assignments,
        "sensors": dataset.sensors,
        "readings": dataset.readings,
        "route_stops": dataset.route_stops,
        "excursions": dataset.excursions,
        "custody_events": dataset.custody_events,
        "corrective_actions": dataset.corrective_actions,
        "excursion_evidence": dataset.excursion_evidence,
    }
    id_attributes = {
        "products": "product_id",
        "policies": "policy_id",
        "shipments": "shipment_id",
        "containers": "container_id",
        "assignments": "assignment_id",
        "sensors": "sensor_id",
        "readings": "reading_id",
        "route_stops": "route_stop_id",
        "excursions": "excursion_id",
        "custody_events": "custody_event_id",
        "corrective_actions": "action_id",
        "excursion_evidence": "evidence_id",
    }
    for name, records in collections.items():
        report.counts[name] = len(records)
        _check_ids(report, name, [getattr(record, id_attributes[name], None) for record in records])
    product_ids = {record.product_id for record in dataset.products}
    policy_ids = {record.policy_id for record in dataset.policies}
    shipment_ids = {record.shipment_id for record in dataset.shipments}
    container_ids = {record.container_id for record in dataset.containers}
    sensor_ids = {record.sensor_id for record in dataset.sensors}
    excursion_ids = {record.excursion_id for record in dataset.excursions}
    excursions_by_id = {record.excursion_id: record for record in dataset.excursions}
    readings_by_id = {record.reading_id: record for record in dataset.readings}
    shipments_by_id = {record.shipment_id: record for record in dataset.shipments}
    sensors_by_id = {record.sensor_id: record for record in dataset.sensors}
    policies_by_id = {record.policy_id: record for record in dataset.policies}
    for policy in dataset.policies:
        if (policy.product_id or policy.product.product_id) not in product_ids:
            report.errors.append(f"policy {policy.policy_id} references missing product")
    for shipment in dataset.shipments:
        if (shipment.product_id or shipment.product.product_id) not in product_ids:
            report.errors.append(f"shipment {shipment.shipment_id} references missing product")
        if shipment.actual_departure and shipment.actual_delivery and shipment.actual_delivery < shipment.actual_departure:
            if shipment.issue_type == "delivery_before_departure":
                report.warnings.append(f"intentional lifecycle anomaly: {shipment.shipment_id}")
            else:
                report.errors.append(
                    f"shipment {shipment.shipment_id} has an unlabeled delivery-before-departure anomaly"
                )
        elif shipment.issue_type == "delivery_before_departure":
            report.errors.append(
                f"shipment {shipment.shipment_id} is labeled delivery-before-departure without inverted timestamps"
            )
    assignments_by_container: dict[str, list] = {}
    assignment_ids = set()
    assignments_by_id = {}
    shipment_assignment_counts: dict[str, int] = {}
    for assignment in dataset.assignments:
        assignment_id = assignment.assignment_id
        assignment_container_id = _related_id(assignment, "container", "container_id")
        assignment_shipment_id = _related_id(assignment, "shipment", "shipment_id")
        assignment_ids.add(assignment_id)
        assignments_by_id[assignment_id] = assignment
        assignments_by_container.setdefault(assignment_container_id, []).append(assignment)
        shipment_assignment_counts[assignment_shipment_id] = (
            shipment_assignment_counts.get(assignment_shipment_id, 0) + 1
        )
        if assignment_container_id not in container_ids:
            report.errors.append(f"assignment {assignment_id} references missing container")
        if assignment_shipment_id not in shipment_ids:
            report.errors.append(f"assignment {assignment_id} references missing shipment")
        if assignment.assigned_to is not None and assignment.assigned_to <= assignment.assigned_from:
            report.errors.append(f"assignment {assignment_id} has an invalid interval")
    for container_id, assignments in assignments_by_container.items():
        ordered = sorted(assignments, key=lambda item: item.assigned_from)
        for previous, current in zip(ordered, ordered[1:]):
            if previous.assigned_to is None or current.assigned_from < previous.assigned_to:
                report.errors.append(f"container {container_id} has overlapping assignments")
    for shipment_id in shipment_ids:
        if shipment_assignment_counts.get(shipment_id, 0) != 1:
            report.errors.append(f"shipment {shipment_id} must have exactly one assignment")
    for sensor in dataset.sensors:
        if _related_id(sensor, "container", "container_id") not in container_ids:
            report.errors.append(f"sensor {sensor.sensor_id} references missing container")
    reading_keys = {
        (reading.sensor_id or reading.sensor.sensor_id, reading.recorded_at)
        for reading in dataset.readings
    }
    if len(reading_keys) != len(dataset.readings):
        report.errors.append("duplicate sensor/timestamp readings detected")
    for reading in dataset.readings:
        reading_sensor_id = _related_id(reading, "sensor", "sensor_id")
        reading_assignment_id = _related_id(reading, "assignment", "assignment_id")
        reading_container_id = reading.container_id or reading.assignment.container_id
        if reading_sensor_id not in sensor_ids:
            report.errors.append(f"reading {reading.reading_id} references missing sensor")
        if reading_assignment_id not in assignment_ids:
            report.errors.append(f"reading {reading.reading_id} references missing assignment")
        assignment = assignments_by_id.get(reading_assignment_id)
        sensor = sensors_by_id.get(reading_sensor_id)
        if assignment is not None:
            if reading_container_id != _related_id(assignment, "container", "container_id"):
                report.errors.append(f"reading {reading.reading_id} has inconsistent container attribution")
            if not _in_interval(reading.recorded_at, assignment.assigned_from, assignment.assigned_to):
                report.errors.append(f"reading {reading.reading_id} falls outside its assignment")
        if sensor is not None and reading_container_id != _related_id(sensor, "container", "container_id"):
            report.errors.append(f"reading {reading.reading_id} has a cross-container sensor reference")
        if sensor is not None and not (
            sensor.calibrated_at <= reading.recorded_at <= sensor.calibration_due_at
        ):
            if reading.issue_type == "calibration_expired":
                report.warnings.append(f"calibration anomaly: {reading.reading_id}")
            else:
                report.errors.append(f"reading {reading.reading_id} is outside sensor calibration")
        expected_unit = "°C" if sensor and sensor.sensor_type.value == "temperature" else "%RH"
        if reading.unit != expected_unit:
            report.errors.append(f"reading {reading.reading_id} has an incompatible unit")
        if reading.recorded_at.tzinfo is None:
            report.errors.append(f"reading {reading.reading_id} has naïve timestamp")
    for excursion in dataset.excursions:
        excursion_shipment_id = _related_id(excursion, "shipment", "shipment_id")
        excursion_sensor_id = _related_id(excursion, "sensor", "sensor_id")
        excursion_policy_id = _related_id(excursion, "policy", "policy_id")
        assignment_id = _related_id(excursion, "assignment", "assignment_id")
        if (
            excursion_shipment_id not in shipment_ids
            or excursion_sensor_id not in sensor_ids
            or excursion_policy_id not in policy_ids
            or assignment_id not in assignment_ids
        ):
            report.errors.append(f"excursion {excursion.excursion_id} has a missing foreign key")
            continue
        assignment = assignments_by_id[assignment_id]
        if _related_id(assignment, "shipment", "shipment_id") != excursion_shipment_id:
            report.errors.append(f"excursion {excursion.excursion_id} crosses shipment assignments")
        if excursion.started_at and excursion.ended_at:
            if excursion.ended_at < excursion.started_at:
                report.errors.append(f"excursion {excursion.excursion_id} ends before it starts")
            calculated = duration_minutes(excursion.started_at, excursion.ended_at)
            if excursion.duration_minutes != calculated:
                report.errors.append(f"excursion {excursion.excursion_id} has inconsistent duration")
        if not _in_interval(excursion.started_at, assignment.assigned_from, assignment.assigned_to):
            report.errors.append(f"excursion {excursion.excursion_id} starts outside its assignment")
        if excursion.ended_at and not _in_interval(
            excursion.ended_at - datetime.resolution,
            assignment.assigned_from,
            assignment.assigned_to,
        ):
            report.errors.append(f"excursion {excursion.excursion_id} ends outside its assignment")
        shipment = shipments_by_id[excursion_shipment_id]
        policy = policies_by_id[excursion_policy_id]
        if _related_id(policy, "product", "product_id") != _related_id(shipment, "product", "product_id"):
            if shipment.issue_type == "wrong_product_threshold":
                report.warnings.append(
                    f"intentional policy anomaly: {excursion.excursion_id}"
                )
            else:
                report.errors.append(
                    f"excursion {excursion.excursion_id} uses a policy for the wrong product"
                )
        if not (policy.effective_from <= excursion.started_at and (
            policy.effective_to is None or excursion.started_at < policy.effective_to
        )):
            report.errors.append(f"excursion {excursion.excursion_id} uses an inactive policy")
    evidence_pairs: set[tuple[str, str]] = set()
    evidence_by_excursion: dict[str, int] = {}
    for evidence in dataset.excursion_evidence:
        excursion = excursions_by_id.get(evidence.excursion_id)
        reading = readings_by_id.get(evidence.reading_id)
        if excursion is None or reading is None:
            report.errors.append(f"evidence {evidence.evidence_id} references missing records")
            continue
        pair = (evidence.excursion_id, evidence.reading_id)
        if pair in evidence_pairs:
            report.errors.append(f"evidence {evidence.evidence_id} duplicates a reading link")
        evidence_pairs.add(pair)
        evidence_by_excursion[evidence.excursion_id] = (
            evidence_by_excursion.get(evidence.excursion_id, 0) + 1
        )
        if reading.sensor_id != excursion.sensor_id:
            report.errors.append(f"evidence {evidence.evidence_id} has an inconsistent sensor")
        if reading.assignment_id != excursion.assignment_id:
            report.errors.append(
                f"evidence {evidence.evidence_id} has an inconsistent assignment"
            )
        if reading.container_id != excursion.container_id:
            report.errors.append(
                f"evidence {evidence.evidence_id} has an inconsistent container"
            )
        reading_assignment = assignments_by_id.get(reading.assignment_id)
        excursion_assignment = assignments_by_id.get(excursion.assignment_id)
        if (
            reading_assignment is None
            or excursion_assignment is None
            or _related_id(reading_assignment, "shipment", "shipment_id")
            != _related_id(excursion_assignment, "shipment", "shipment_id")
        ):
            report.errors.append(
                f"evidence {evidence.evidence_id} has an inconsistent shipment"
            )
        if reading.recorded_at < excursion.started_at or (
            excursion.ended_at is not None
            and reading.recorded_at > excursion.ended_at
        ):
            report.errors.append(f"evidence {evidence.evidence_id} falls outside its excursion")
    for excursion_id in excursion_ids:
        if evidence_by_excursion.get(excursion_id, 0) == 0:
            report.errors.append(f"excursion {excursion_id} has no evidence readings")
    for action in dataset.corrective_actions:
        if (action.excursion_id or action.excursion.excursion_id) not in excursion_ids:
            report.errors.append(f"action {action.action_id} references missing excursion")
    for shipment_id, stops in _group_by_shipment(dataset.route_stops).items():
        ordered = sorted(stops, key=lambda item: item.sequence_number)
        shipment = shipments_by_id.get(shipment_id)
        for previous, current in zip(ordered, ordered[1:]):
            if current.sequence_number <= previous.sequence_number:
                report.errors.append(f"shipment {shipment_id} has invalid route sequencing")
            if (
                shipment is not None
                and shipment.issue_type != "delivery_before_departure"
                and
                previous.actual_departure is not None
                and current.actual_arrival is not None
                and current.actual_arrival < previous.actual_departure
            ):
                report.errors.append(f"shipment {shipment_id} has route chronology overlap")
    for shipment_id, events in _group_by_shipment(dataset.custody_events).items():
        ordered = sorted(events, key=lambda item: item.event_time)
        if any(current.event_time < previous.event_time for previous, current in zip(ordered, ordered[1:])):
            report.errors.append(f"shipment {shipment_id} has invalid custody chronology")
    if require_scenario_coverage:
        scenario_types = {case.scenario_type for case in dataset.ground_truth}
        missing = set(SCENARIO_TYPES) - scenario_types
        if missing:
            report.errors.append(f"missing scenario coverage: {sorted(missing)}")
    return report


def _related_id(record: object, relationship_name: str, identifier: str) -> str | None:
    value = getattr(record, identifier, None)
    if value is not None:
        return value
    related = getattr(record, relationship_name, None)
    return getattr(related, identifier, None) if related is not None else None


def _in_interval(value: datetime, start: datetime, end: datetime | None) -> bool:
    return value >= start and (end is None or value < end)


def _group_by_shipment(records: Iterable[object]) -> dict[str, list[object]]:
    grouped: dict[str, list[object]] = {}
    for record in records:
        shipment_id = _related_id(record, "shipment", "shipment_id")
        if shipment_id is not None:
            grouped.setdefault(shipment_id, []).append(record)
    return grouped


def _check_ids(report: ValidationReport, entity: str, identifiers: Iterable[str | None]) -> None:
    values = list(identifiers)
    if any(identifier is None for identifier in values):
        report.errors.append(f"{entity} contains a record without an identifier")
    normalized = [identifier for identifier in values if identifier is not None]
    if len(normalized) != len(set(normalized)):
        report.errors.append(f"{entity} contains duplicate identifiers")
