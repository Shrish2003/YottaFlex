from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
from typing import Any

from backend.app.core.time import duration_minutes, to_utc
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
from backend.app.models.enums import (
    ContainerStatus,
    CorrectiveActionStatus,
    CorrectiveActionType,
    CustodyEventType,
    ExcursionSeverity,
    ExcursionStatus,
    ReadingQualityStatus,
    RouteStopStatus,
    SensorStatus,
    SensorType,
    ShipmentStatus,
)


SCENARIO_TYPES = (
    "normal",
    "brief_excursion",
    "prolonged_excursion",
    "sensor_dropout",
    "calibration_failure",
    "route_delay",
    "physically_invalid_reading",
    "missing_interval",
    "delivery_before_departure",
    "wrong_product_threshold",
    "duration_undercounted",
)

SCENARIO_EXCURSION_DURATIONS = {
    "brief_excursion": 10,
    "prolonged_excursion": 60,
    "duration_undercounted": 5,
    "wrong_product_threshold": 5,
}


@dataclass(frozen=True)
class ProductSpec:
    name: str
    category: str
    min_temp_c: Decimal
    max_temp_c: Decimal
    max_excursion_minutes: int
    min_humidity_pct: Decimal | None = None
    max_humidity_pct: Decimal | None = None


@dataclass(frozen=True)
class GeneratorConfig:
    shipment_count: int
    container_count: int
    scenario_counts: dict[str, int]
    products: tuple[ProductSpec, ...]
    seed: int = 20261022
    sampling_interval_minutes: int = 5
    min_trip_days: int = 2
    max_trip_days: int = 5
    start_datetime: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)
    generator_version: str = "module-3-v1"

    def __post_init__(self) -> None:
        if self.shipment_count <= 0 or self.container_count <= 0:
            raise ValueError("shipment_count and container_count must be positive")
        if self.sampling_interval_minutes <= 0:
            raise ValueError("sampling_interval_minutes must be positive")
        if self.min_trip_days <= 0 or self.max_trip_days < self.min_trip_days:
            raise ValueError("trip-day bounds are invalid")
        if not self.products:
            raise ValueError("at least one product specification is required")
        if to_utc(self.start_datetime) != self.start_datetime.astimezone(timezone.utc):
            raise ValueError("start_datetime normalization failed")
        if set(self.scenario_counts) - set(SCENARIO_TYPES):
            raise ValueError("scenario_counts contains an unknown scenario")
        if any(count < 0 for count in self.scenario_counts.values()):
            raise ValueError("scenario counts must not be negative")
        if sum(self.scenario_counts.values()) != self.shipment_count:
            raise ValueError("scenario counts must sum to shipment_count")
        for product in self.products:
            if product.min_temp_c > product.max_temp_c:
                raise ValueError("product temperature limits are invalid")
            if (product.min_humidity_pct is None) != (product.max_humidity_pct is None):
                raise ValueError("humidity limits must be provided as a pair")
            if product.max_excursion_minutes < 0:
                raise ValueError("max_excursion_minutes must not be negative")


@dataclass
class GroundTruthCase:
    case_id: str
    entity_ids: dict[str, str]
    scenario_type: str
    expected_detector_decision: str
    expected_issue_or_excursion: str
    expected_policy_id: str | None
    expected_duration_minutes: int | None
    rationale: str


@dataclass
class GeneratedDataset:
    products: list[Product] = field(default_factory=list)
    policies: list[ThresholdPolicy] = field(default_factory=list)
    shipments: list[Shipment] = field(default_factory=list)
    containers: list[Container] = field(default_factory=list)
    sensors: list[Sensor] = field(default_factory=list)
    readings: list[SensorReading] = field(default_factory=list)
    route_stops: list[RouteStop] = field(default_factory=list)
    excursions: list[Excursion] = field(default_factory=list)
    custody_events: list[CustodyEvent] = field(default_factory=list)
    corrective_actions: list[CorrectiveAction] = field(default_factory=list)
    ground_truth: list[GroundTruthCase] = field(default_factory=list)
    assignments: list[ContainerAssignment] = field(default_factory=list)
    excursion_evidence: list[ExcursionEvidence] = field(default_factory=list)
    config: GeneratorConfig | None = None

    def operational_collections(self) -> list[list[Any]]:
        return [
            self.products,
            self.policies,
            self.shipments,
            self.containers,
            self.assignments,
            self.sensors,
            self.readings,
            self.route_stops,
            self.excursions,
            self.excursion_evidence,
            self.custody_events,
            self.corrective_actions,
        ]


def generate_dataset(config: GeneratorConfig) -> GeneratedDataset:
    rng = random.Random(config.seed)
    dataset = GeneratedDataset(config=config)
    product_models: list[Product] = []
    policy_models: list[ThresholdPolicy] = []
    for index, spec in enumerate(config.products, 1):
        product = Product(
            product_id=f"PRD-{index:06d}",
            name=spec.name,
            category=spec.category,
            active=True,
        )
        policy = ThresholdPolicy(
            policy_id=f"POL-{index:06d}",
            product=product,
            min_temp_c=spec.min_temp_c,
            max_temp_c=spec.max_temp_c,
            max_excursion_minutes=spec.max_excursion_minutes,
            min_humidity_pct=spec.min_humidity_pct,
            max_humidity_pct=spec.max_humidity_pct,
            effective_from=to_utc(config.start_datetime),
            version=1,
        )
        product_models.append(product)
        policy_models.append(policy)
    dataset.products = product_models
    dataset.policies = policy_models
    configured_product_count = len(product_models)
    if "wrong_product_threshold" in config.scenario_counts and len(product_models) == 1:
        wrong_product = Product(
            product_id="PRD-000002",
            name="Wrong product fixture",
            category="synthetic_control",
            active=True,
        )
        wrong_policy = ThresholdPolicy(
            policy_id="POL-000002",
            product=wrong_product,
            min_temp_c=Decimal("20"),
            max_temp_c=Decimal("30"),
            max_excursion_minutes=policy_models[0].max_excursion_minutes,
            effective_from=to_utc(config.start_datetime),
            version=1,
        )
        dataset.products.append(wrong_product)
        dataset.policies.append(wrong_policy)

    scenarios = [
        scenario
        for scenario, count in sorted(config.scenario_counts.items())
        for _ in range(count)
    ]
    rng.shuffle(scenarios)
    for container_number in range(1, config.container_count + 1):
        container = Container(
            container_id=f"CNT-{container_number:06d}",
            container_type="validated",
            status=ContainerStatus.PREPARED,
        )
        dataset.containers.append(container)
        dataset.sensors.extend(
            [
                Sensor(
                    sensor_id=f"SNS-CNT-{container_number:06d}-TEMP",
                    container=container,
                    sensor_type=SensorType.TEMPERATURE,
                    calibrated_at=to_utc(config.start_datetime) - timedelta(days=30),
                    calibration_due_at=to_utc(config.start_datetime)
                    + timedelta(days=config.shipment_count + config.max_trip_days),
                    status=SensorStatus.ACTIVE,
                ),
                Sensor(
                    sensor_id=f"SNS-CNT-{container_number:06d}-HUM",
                    container=container,
                    sensor_type=SensorType.HUMIDITY,
                    calibrated_at=to_utc(config.start_datetime) - timedelta(days=30),
                    calibration_due_at=to_utc(config.start_datetime)
                    + timedelta(days=config.shipment_count + config.max_trip_days),
                    status=SensorStatus.ACTIVE,
                ),
            ]
        )

    container_available_at = {
        container.container_id: to_utc(config.start_datetime)
        for container in dataset.containers
    }
    cal_fail_count = config.scenario_counts.get("calibration_failure", 0)
    if cal_fail_count > 0 and len(dataset.containers) > cal_fail_count:
        general_containers = dataset.containers[:-cal_fail_count]
        cal_fail_containers = dataset.containers[-cal_fail_count:]
    else:
        general_containers = dataset.containers
        cal_fail_containers = dataset.containers

    for shipment_number, scenario in enumerate(scenarios, 1):
        product_index = (shipment_number - 1) % configured_product_count
        product = product_models[product_index]
        policy = policy_models[product_index]
        operational_policy = policy
        expected_policy_id = policy.policy_id
        if scenario == "wrong_product_threshold":
            operational_policy = policy_models[(product_index + 1) % len(policy_models)]
        trip_days = rng.randint(config.min_trip_days, config.max_trip_days)
        planned_departure = to_utc(config.start_datetime) + timedelta(days=shipment_number - 1)
        planned_delivery = planned_departure + timedelta(days=trip_days)
        actual_departure = planned_departure + timedelta(minutes=rng.randint(0, 60))
        actual_delivery = actual_departure + timedelta(days=trip_days, minutes=rng.randint(0, 180))
        if scenario == "route_delay":
            route_delay = timedelta(hours=6)
            actual_departure += route_delay
            actual_delivery += route_delay
        if scenario == "delivery_before_departure":
            actual_delivery = actual_departure - timedelta(minutes=5)
        status = ShipmentStatus.DELIVERED
        shipment = Shipment(
            shipment_id=f"SHP-{planned_departure.year}-{shipment_number:06d}",
            product=product,
            origin=f"Origin-{shipment_number:03d}",
            destination=f"Destination-{shipment_number:03d}",
            planned_departure=planned_departure,
            planned_delivery=planned_delivery,
            actual_departure=actual_departure,
            actual_delivery=actual_delivery,
            issue_type=(
                "delivery_before_departure"
                if scenario == "delivery_before_departure"
                else "wrong_product_threshold"
                if scenario == "wrong_product_threshold"
                else None
            ),
            status=status,
        )
        dataset.shipments.append(shipment)

        if scenario == "calibration_failure":
            available_cal = [
                c
                for c in cal_fail_containers
                if container_available_at[c.container_id] <= planned_departure
            ]
            if not available_cal:
                raise ValueError(
                    "cal_fail_containers count is insufficient for non-overlapping assignment intervals"
                )
            container = available_cal[0]
            for sensor in container.sensors:
                if sensor.sensor_type == SensorType.TEMPERATURE:
                    sensor.status = SensorStatus.FAULTY
                    sensor.calibration_due_at = planned_departure - timedelta(minutes=1)
            container_available_at[container.container_id] = datetime.max.replace(
                tzinfo=timezone.utc
            )
        else:
            available_gen = [
                c
                for c in general_containers
                if container_available_at[c.container_id] <= planned_departure
            ]
            if not available_gen:
                raise ValueError(
                    "container_count is insufficient for non-overlapping assignment intervals"
                )
            container = available_gen[shipment_number % len(available_gen)]
            container_available_at[container.container_id] = planned_delivery
        assignment = ContainerAssignment(
            assignment_id=f"ASN-{planned_departure.year}-{shipment_number:06d}",
            container=container,
            shipment=shipment,
            assigned_from=planned_departure,
            assigned_to=planned_delivery,
        )
        dataset.assignments.append(assignment)
        temp_sensor = next(
            sensor for sensor in container.sensors
            if sensor.sensor_type == SensorType.TEMPERATURE
        )
        humidity_sensor = next(
            sensor for sensor in container.sensors
            if sensor.sensor_type == SensorType.HUMIDITY
        )
        _generate_readings(
            dataset,
            assignment,
            temp_sensor,
            humidity_sensor,
            operational_policy,
            planned_departure,
            planned_delivery,
            config,
            scenario,
        )
        _generate_route_and_custody(
            dataset,
            shipment,
            planned_departure,
            planned_delivery,
            actual_departure,
            actual_delivery,
            scenario,
        )
        _generate_scenario_records(
            dataset,
            shipment,
            assignment,
            temp_sensor,
            operational_policy,
            planned_departure,
            scenario,
            expected_policy_id=expected_policy_id,
        )

    return dataset


def _generate_readings(
    dataset: GeneratedDataset,
    assignment: ContainerAssignment,
    temp_sensor: Sensor,
    humidity_sensor: Sensor,
    policy: ThresholdPolicy,
    start: datetime,
    end: datetime,
    config: GeneratorConfig,
    scenario: str,
) -> None:
    rng = random.Random(config.seed + len(dataset.shipments) * 1009)
    interval = timedelta(minutes=config.sampling_interval_minutes)
    timestamp = start
    index = 0
    while timestamp < end:
        skip_temp = scenario in {"sensor_dropout", "missing_interval"} and 3 <= index <= 5
        if not skip_temp:
            temp_value = Decimal("5") + Decimal(str(round(rng.uniform(-0.4, 0.4), 3)))
            quality = ReadingQualityStatus.SUSPECT if scenario == "calibration_failure" else ReadingQualityStatus.VALID
            issue = (
                "calibration_expired"
                if scenario == "calibration_failure"
                else "sensor_dropout"
                if scenario == "sensor_dropout" and index in {2, 6}
                else None
            )
            if scenario == "physically_invalid_reading" and index == 2:
                temp_value = Decimal("-999")
                quality = ReadingQualityStatus.INVALID
                issue = "physically_invalid_range"
            if scenario in {"brief_excursion", "prolonged_excursion", "missing_interval", "duration_undercounted"} and 4 <= index <= 6:
                temp_value = policy.max_temp_c + Decimal("1.5")
            if scenario == "prolonged_excursion" and 4 <= index <= 12:
                temp_value = policy.max_temp_c + Decimal("1.5")
            dataset.readings.append(
                SensorReading(
                    reading_id=f"RDG-{temp_sensor.sensor_id}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}",
                    assignment_id=assignment.assignment_id,
                    container_id=assignment.container.container_id,
                    sensor_id=temp_sensor.sensor_id,
                    recorded_at=timestamp,
                    value=temp_value,
                    unit="°C",
                    quality_status=quality,
                    issue_type=issue,
                )
            )
        humidity_value = Decimal("50") + Decimal(str(round(rng.uniform(-2, 2), 3)))
        dataset.readings.append(
            SensorReading(
                reading_id=f"RDG-{humidity_sensor.sensor_id}-{timestamp.strftime('%Y%m%dT%H%M%SZ')}",
                assignment_id=assignment.assignment_id,
                container_id=assignment.container.container_id,
                sensor_id=humidity_sensor.sensor_id,
                recorded_at=timestamp,
                value=humidity_value,
                unit="%RH",
                quality_status=ReadingQualityStatus.VALID,
            )
        )
        timestamp += interval
        index += 1


def _generate_route_and_custody(
    dataset: GeneratedDataset,
    shipment: Shipment,
    planned_departure: datetime,
    planned_delivery: datetime,
    actual_departure: datetime,
    actual_delivery: datetime,
    scenario: str,
) -> None:
    delay = timedelta(hours=6) if scenario == "route_delay" else timedelta(0)
    for sequence in range(1, 3):
        planned_arrival = planned_departure + (
            planned_delivery - planned_departure
        ) * sequence / 3
        arrival = planned_arrival + delay
        dataset.route_stops.append(
            RouteStop(
                route_stop_id=f"RST-{len(dataset.route_stops) + 1:06d}",
                shipment=shipment,
                sequence_number=sequence,
                location=f"Hub-{sequence}",
                planned_arrival=planned_arrival,
                actual_arrival=arrival,
                actual_departure=arrival + timedelta(minutes=30),
                status=RouteStopStatus.DEPARTED,
            )
        )
    dataset.custody_events.extend(
        [
            CustodyEvent(
                custody_event_id=f"CUS-{len(dataset.custody_events) + 1:06d}",
                shipment=shipment,
                event_time=actual_departure,
                event_type=CustodyEventType.DISPATCHED,
                to_party="carrier",
                location=shipment.origin,
            ),
            CustodyEvent(
                custody_event_id=f"CUS-{len(dataset.custody_events) + 2:06d}",
                shipment=shipment,
                event_time=actual_delivery,
                event_type=CustodyEventType.RECEIVED,
                from_party="carrier",
                to_party="warehouse",
                location=shipment.destination,
            ),
        ]
    )


def _generate_scenario_records(
    dataset: GeneratedDataset,
    shipment: Shipment,
    assignment: ContainerAssignment,
    sensor: Sensor | None,
    policy: ThresholdPolicy,
    start: datetime,
    scenario: str,
    *,
    expected_policy_id: str | None = None,
) -> None:
    scenario_case = f"SCN-{len(dataset.ground_truth) + 1:06d}"
    issue = "none"
    decision = "no_excursion"
    expected_duration = None
    policy_id: str | None = (
        policy.policy_id if expected_policy_id is None else expected_policy_id
    )
    if scenario in {"brief_excursion", "prolonged_excursion", "duration_undercounted", "wrong_product_threshold"}:
        duration = SCENARIO_EXCURSION_DURATIONS[scenario]
        excursion = Excursion(
                excursion_id=f"EXC-{start.year}-{len(dataset.excursions) + 1:06d}",
                assignment_id=assignment.assignment_id,
                container_id=assignment.container.container_id,
                shipment_id=shipment.shipment_id,
                sensor_id=sensor.sensor_id if sensor else "",
                policy_id=policy.policy_id,
                started_at=start + timedelta(minutes=20),
                ended_at=start + timedelta(minutes=20 + duration),
                duration_minutes=duration_minutes(
                    start + timedelta(minutes=20),
                    start + timedelta(minutes=20 + duration),
                ),
                severity=(
                    ExcursionSeverity.CRITICAL
                    if duration_minutes(
                        start + timedelta(minutes=20),
                        start + timedelta(minutes=20 + duration),
                    )
                    > policy.max_excursion_minutes
                    else ExcursionSeverity.WARNING
                ),
                status=ExcursionStatus.OPEN,
                decision_reason="Generated scenario fixture; not a detector decision",
            )
        dataset.excursions.append(excursion)
        for reading in dataset.readings:
            if (
                reading.sensor_id == excursion.sensor_id
                and excursion.started_at <= reading.recorded_at <= excursion.ended_at
            ):
                dataset.excursion_evidence.append(
                    ExcursionEvidence(
                        evidence_id=f"EVD-{excursion.excursion_id}-{reading.reading_id}",
                        excursion_id=excursion.excursion_id,
                        reading_id=reading.reading_id,
                        excursion=excursion,
                        reading=reading,
                    )
                )
        dataset.corrective_actions.append(
            CorrectiveAction(
                action_id=f"ACT-{len(dataset.corrective_actions) + 1:06d}",
                excursion=excursion,
                assigned_to="quality_review",
                action_type=CorrectiveActionType.REVIEW,
                description="Review generated scenario evidence.",
                created_at=start + timedelta(minutes=20),
                status=CorrectiveActionStatus.OPEN,
            )
        )
        if scenario == "wrong_product_threshold":
            decision = "policy_selection_issue"
            issue = "wrong_product_threshold"
            expected_duration = None
        else:
            decision = "excursion_expected"
            issue = "temperature_excursion"
            expected_duration = None if scenario == "duration_undercounted" else duration
    elif scenario == "physically_invalid_reading":
        issue = "physically_invalid_range"
        decision = "data_quality_issue"
    elif scenario in {"sensor_dropout", "missing_interval"}:
        issue = "missing_reading_interval"
        decision = "data_quality_issue"
    elif scenario == "calibration_failure":
        issue = "calibration_failure"
        decision = "suspect_readings"
    elif scenario == "route_delay":
        issue = "route_delay"
        decision = "route_delay"
    elif scenario == "delivery_before_departure":
        issue = "delivery_before_departure"
        decision = "lifecycle_issue"
    elif scenario == "wrong_product_threshold":
        issue = "wrong_product_threshold"
        decision = "policy_selection_issue"
    dataset.ground_truth.append(
        GroundTruthCase(
            case_id=scenario_case,
            entity_ids={"shipment_id": shipment.shipment_id, "sensor_id": sensor.sensor_id if sensor else ""},
            scenario_type=scenario,
            expected_detector_decision=decision,
            expected_issue_or_excursion=issue,
            expected_policy_id=policy_id,
            expected_duration_minutes=expected_duration,
            rationale="Synthetic labelled scenario; excluded from detector inputs.",
        )
    )
