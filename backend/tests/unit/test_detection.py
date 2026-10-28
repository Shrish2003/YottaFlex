import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.app.models.entities import (
    Container,
    ContainerAssignment,
    Excursion,
    ExcursionEvidence,
    Product,
    Sensor,
    SensorReading,
    Shipment,
    ThresholdPolicy,
)
from backend.app.models.enums import (
    ContainerStatus,
    ExcursionSeverity,
    ExcursionStatus,
    ReadingQualityStatus,
    SensorStatus,
    SensorType,
    ShipmentStatus,
)
from backend.app.services.detection import DetectorConfig, detect_dataset
from backend.app.services.generator import GeneratedDataset


UTC = timezone.utc


def make_dataset(values: list[Decimal], *, quality=ReadingQualityStatus.VALID):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    product = Product(product_id="PRD-1", name="Test", category="cold", active=True)
    policy = ThresholdPolicy(
        policy_id="POL-1",
        product_id=product.product_id,
        product=product,
        min_temp_c=Decimal("2"),
        max_temp_c=Decimal("8"),
        max_excursion_minutes=30,
        effective_from=start,
        version=1,
    )
    container = Container(
        container_id="CNT-1",
        container_type="validated",
        status=ContainerStatus.PREPARED,
    )
    shipment = Shipment(
        shipment_id="SHP-1",
        product_id=product.product_id,
        product=product,
        origin="A",
        destination="B",
        planned_departure=start,
        planned_delivery=start + timedelta(hours=1),
        actual_departure=start,
        actual_delivery=start + timedelta(hours=1),
        status=ShipmentStatus.DELIVERED,
    )
    assignment = ContainerAssignment(
        assignment_id="ASN-1",
        container_id=container.container_id,
        shipment_id=shipment.shipment_id,
        container=container,
        shipment=shipment,
        assigned_from=start,
        assigned_to=start + timedelta(hours=1),
    )
    sensor = Sensor(
        sensor_id="SNS-1",
        container_id=container.container_id,
        container=container,
        sensor_type=SensorType.TEMPERATURE,
        calibrated_at=start - timedelta(days=1),
        calibration_due_at=start + timedelta(days=1),
        status=SensorStatus.ACTIVE,
    )
    readings = [
        SensorReading(
            reading_id=f"RDG-{index}",
            assignment_id=assignment.assignment_id,
            assignment=assignment,
            container_id=container.container_id,
            sensor_id=sensor.sensor_id,
            sensor=sensor,
            recorded_at=start + timedelta(minutes=5 * index),
            value=value,
            unit="°C",
            quality_status=quality,
        )
        for index, value in enumerate(values)
    ]
    return GeneratedDataset(
        products=[product],
        policies=[policy],
        shipments=[shipment],
        containers=[container],
        sensors=[sensor],
        readings=readings,
        assignments=[assignment],
        config=None,
    )


class DetectionTests(unittest.TestCase):
    def test_exact_boundaries_are_compliant(self):
        report = detect_dataset(make_dataset([Decimal("2"), Decimal("8")]))
        self.assertFalse(any(f.finding_type == "threshold_excursion" for f in report.findings))

    def test_out_of_range_readings_form_explainable_excursion(self):
        report = detect_dataset(make_dataset([Decimal("5"), Decimal("9"), Decimal("9")]))
        excursions = [f for f in report.findings if f.finding_type == "threshold_excursion"]
        self.assertEqual(len(excursions), 1)
        self.assertEqual(excursions[0].reading_ids, ("RDG-1", "RDG-2"))
        self.assertEqual(excursions[0].policy_id, "POL-1")
        self.assertEqual(excursions[0].shipment_id, "SHP-1")
        self.assertIsNone(excursions[0].duration_minutes)

    def test_compliant_recovery_closes_excursion_with_duration(self):
        report = detect_dataset(make_dataset([Decimal("9"), Decimal("9"), Decimal("5")]))
        excursion = next(
            finding
            for finding in report.findings
            if finding.finding_type == "threshold_excursion"
        )
        self.assertEqual(excursion.ended_at, datetime(2026, 1, 1, 0, 10, tzinfo=UTC))
        self.assertEqual(excursion.duration_minutes, 10)
        self.assertEqual(excursion.status, "under_review")

    def test_calibration_invalid_reading_is_not_excursion(self):
        dataset = make_dataset([Decimal("9")])
        dataset.sensors[0].calibration_due_at = dataset.readings[0].recorded_at - timedelta(minutes=1)
        report = detect_dataset(dataset)
        self.assertTrue(any(f.finding_type == "calibration_failure" for f in report.findings))
        self.assertFalse(any(f.finding_type == "threshold_excursion" for f in report.findings))

    def test_missing_interval_is_unknown_and_breaks_excursion_group(self):
        dataset = make_dataset([Decimal("9"), Decimal("9"), Decimal("9")])
        dataset.readings[2].recorded_at += timedelta(minutes=5)
        report = detect_dataset(dataset)
        self.assertTrue(any(f.finding_type == "telemetry_gap" for f in report.findings))
        excursions = [f for f in report.findings if f.finding_type == "threshold_excursion"]
        self.assertEqual(len(excursions), 2)

    def test_assignment_end_is_exclusive(self):
        dataset = make_dataset([Decimal("5")])
        dataset.readings[0].recorded_at = dataset.assignments[0].assigned_to
        report = detect_dataset(dataset)
        self.assertTrue(any(f.finding_type == "invalid_attribution" for f in report.findings))

    def test_invalid_quality_and_lifecycle_are_reported(self):
        dataset = make_dataset([Decimal("9")], quality=ReadingQualityStatus.INVALID)
        dataset.shipments[0].actual_delivery = dataset.shipments[0].actual_departure - timedelta(minutes=1)
        report = detect_dataset(dataset)
        kinds = {finding.finding_type for finding in report.findings}
        self.assertIn("invalid_reading", kinds)
        self.assertIn("lifecycle_anomaly", kinds)
        self.assertNotIn("threshold_excursion", kinds)

    def test_same_operational_input_is_deterministic(self):
        first = detect_dataset(make_dataset([Decimal("5"), Decimal("9")]))
        second = detect_dataset(make_dataset([Decimal("5"), Decimal("9")]))
        self.assertEqual(first, second)

    def test_duplicate_reading_and_existing_excursion_are_deduplicated(self):
        dataset = make_dataset([Decimal("9"), Decimal("9")])
        existing = Excursion(
            excursion_id="EXC-1",
            assignment_id="ASN-1",
            container_id="CNT-1",
            shipment_id="SHP-1",
            sensor_id="SNS-1",
            policy_id="POL-1",
            started_at=dataset.readings[0].recorded_at,
            ended_at=dataset.readings[1].recorded_at,
            duration_minutes=5,
            severity=ExcursionSeverity.WARNING,
            status=ExcursionStatus.OPEN,
            decision_reason="existing operational record",
        )
        dataset.excursions = [existing]
        duplicate = dataset.readings[1]
        dataset.readings.append(
            SensorReading(
                reading_id="RDG-DUPLICATE",
                assignment_id=duplicate.assignment_id,
                container_id=duplicate.container_id,
                sensor_id=duplicate.sensor_id,
                sensor=duplicate.sensor,
                assignment=duplicate.assignment,
                recorded_at=duplicate.recorded_at,
                value=duplicate.value,
                unit=duplicate.unit,
                quality_status=duplicate.quality_status,
            )
        )
        report = detect_dataset(dataset)
        findings = [f for f in report.findings if f.finding_type == "threshold_excursion"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].excursion_id, "EXC-1")
        self.assertTrue(any(f.finding_type == "duplicate_reading" for f in report.findings))

    def test_duplicate_evidence_link_is_reported(self):
        dataset = make_dataset([Decimal("9")])
        dataset.excursions = [
            Excursion(
                excursion_id="EXC-1",
                assignment_id="ASN-1",
                container_id="CNT-1",
                shipment_id="SHP-1",
                sensor_id="SNS-1",
                policy_id="POL-1",
                started_at=dataset.readings[0].recorded_at,
                ended_at=None,
                duration_minutes=None,
                severity=ExcursionSeverity.WARNING,
                status=ExcursionStatus.OPEN,
                decision_reason="existing operational record",
            )
        ]
        dataset.excursion_evidence = [
            ExcursionEvidence(
                evidence_id="EVD-1",
                excursion_id="EXC-1",
                reading_id="RDG-0",
            ),
            ExcursionEvidence(
                evidence_id="EVD-2",
                excursion_id="EXC-1",
                reading_id="RDG-0",
            ),
        ]
        report = detect_dataset(dataset)
        self.assertTrue(any(f.finding_type == "duplicate_evidence" for f in report.findings))

    def test_invalid_detector_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            DetectorConfig(sampling_interval_minutes=0)

    def test_route_delay_detected(self):
        dataset = make_dataset([Decimal("5")])
        dataset.shipments[0].actual_delivery = dataset.shipments[0].planned_delivery + timedelta(hours=6)
        report = detect_dataset(dataset)
        delays = [f for f in report.findings if f.finding_type == "route_delay"]
        self.assertEqual(len(delays), 1)
        self.assertEqual(delays[0].shipment_id, "SHP-1")

    def test_policy_selection_error_on_mismatched_excursion(self):
        dataset = make_dataset([Decimal("5")])
        other_product = Product(product_id="PRD-OTHER", name="Other", category="cold", active=True)
        wrong_policy = ThresholdPolicy(
            policy_id="POL-WRONG",
            product_id=other_product.product_id,
            product=other_product,
            min_temp_c=Decimal("15"),
            max_temp_c=Decimal("25"),
            max_excursion_minutes=30,
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )
        dataset.policies.append(wrong_policy)
        dataset.excursions = [
            Excursion(
                excursion_id="EXC-WRONG",
                assignment_id="ASN-1",
                container_id="CNT-1",
                shipment_id="SHP-1",
                sensor_id="SNS-1",
                policy_id="POL-WRONG",
                started_at=dataset.readings[0].recorded_at,
                ended_at=None,
                duration_minutes=None,
                severity=ExcursionSeverity.WARNING,
                status=ExcursionStatus.OPEN,
                decision_reason="test",
            )
        ]
        report = detect_dataset(dataset)
        policy_errors = [f for f in report.findings if f.finding_type == "policy_selection_error"]
        self.assertEqual(len(policy_errors), 1)
        self.assertEqual(policy_errors[0].shipment_id, "SHP-1")


if __name__ == "__main__":
    unittest.main()
