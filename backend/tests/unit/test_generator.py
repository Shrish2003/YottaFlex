import unittest
from datetime import timedelta
from decimal import Decimal

from backend.app.services.generator import (
    GeneratorConfig,
    ProductSpec,
    SCENARIO_TYPES,
    generate_dataset,
)
from backend.app.services.validation import validate_dataset


def config(seed: int = 20261022) -> GeneratorConfig:
    return GeneratorConfig(
        seed=seed,
        shipment_count=len(SCENARIO_TYPES),
        container_count=len(SCENARIO_TYPES),
        scenario_counts={scenario: 1 for scenario in SCENARIO_TYPES},
        products=(
            ProductSpec(
                name="Test product",
                category="cold_chain",
                min_temp_c=Decimal("2"),
                max_temp_c=Decimal("8"),
                max_excursion_minutes=30,
                min_humidity_pct=Decimal("30"),
                max_humidity_pct=Decimal("70"),
            ),
        ),
    )


class GeneratorTests(unittest.TestCase):
    def test_same_seed_has_same_logical_export_shape(self) -> None:
        first = generate_dataset(config())
        second = generate_dataset(config())
        self.assertEqual(
            [(item.shipment_id, item.planned_departure) for item in first.shipments],
            [(item.shipment_id, item.planned_departure) for item in second.shipments],
        )
        self.assertEqual(
            [(item.reading_id, item.value) for item in first.readings],
            [(item.reading_id, item.value) for item in second.readings],
        )

    def test_different_seed_changes_telemetry(self) -> None:
        first = generate_dataset(config(1))
        second = generate_dataset(config(2))
        self.assertNotEqual([item.value for item in first.readings], [item.value for item in second.readings])

    def test_all_entities_and_scenarios_are_generated(self) -> None:
        dataset = generate_dataset(config())
        self.assertTrue(all(dataset.operational_collections()))
        self.assertEqual({case.scenario_type for case in dataset.ground_truth}, set(SCENARIO_TYPES))
        self.assertTrue(validate_dataset(dataset).passed)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"normal": 2},
                products=(
                    ProductSpec("x", "y", Decimal("8"), Decimal("2"), 30),
                ),
            )

    def test_calibration_failure_has_faulty_sensor_and_expired_readings(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"calibration_failure": 1},
                products=config().products,
            )
        )
        temperature_sensor = next(
            sensor for sensor in dataset.sensors if sensor.sensor_type.value == "temperature"
        )
        readings = [
            reading
            for reading in dataset.readings
            if reading.sensor_id == temperature_sensor.sensor_id
        ]
        self.assertEqual(temperature_sensor.status.value, "faulty")
        self.assertTrue(all(reading.quality_status.value == "suspect" for reading in readings))
        self.assertTrue(all(reading.issue_type == "calibration_expired" for reading in readings))
        self.assertTrue(
            all(reading.recorded_at > temperature_sensor.calibration_due_at for reading in readings)
        )
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertTrue(report.passed, report.errors)
        self.assertTrue(any("calibration anomaly" in warning for warning in report.warnings))
        normal = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"normal": 1},
                products=config().products,
            )
        )
        normal_sensor = next(
            sensor for sensor in normal.sensors if sensor.sensor_type.value == "temperature"
        )
        self.assertTrue(
            all(
                sensor.calibrated_at <= reading.recorded_at <= sensor.calibration_due_at
                for reading in normal.readings
                for sensor in normal.sensors
                if sensor.sensor_id == reading.sensor_id
            )
        )

    def test_wrong_product_threshold_uses_policy_for_different_product(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"wrong_product_threshold": 1},
                products=config().products,
            )
        )
        shipment = dataset.shipments[0]
        excursion = dataset.excursions[0]
        shipment_product_id = shipment.product_id or shipment.product.product_id
        policy = next(policy for policy in dataset.policies if policy.policy_id == excursion.policy_id)
        self.assertNotEqual(policy.product_id, shipment_product_id)

    def test_sensor_dropout_is_distinct_from_missing_interval(self) -> None:
        dropout = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"sensor_dropout": 1},
                products=config().products,
            )
        )
        missing = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"missing_interval": 1},
                products=config().products,
            )
        )
        dropout_issues = {
            reading.issue_type
            for reading in dropout.readings
            if reading.issue_type is not None
        }
        missing_issues = {
            reading.issue_type
            for reading in missing.readings
            if reading.issue_type is not None
        }
        self.assertIn("sensor_dropout", dropout_issues)
        self.assertNotIn("sensor_dropout", missing_issues)

    def test_route_delay_preserves_plan_and_delays_execution(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"route_delay": 1},
                products=config().products,
            )
        )
        shipment = dataset.shipments[0]
        stops = sorted(dataset.route_stops, key=lambda stop: stop.sequence_number)
        self.assertGreater(shipment.actual_departure, shipment.planned_departure)
        self.assertGreater(shipment.actual_delivery, shipment.planned_delivery)
        self.assertTrue(
            all(stop.actual_arrival > stop.planned_arrival for stop in stops)
        )
        self.assertTrue(
            all(
                stop.actual_departure >= stop.actual_arrival
                for stop in stops
            )
        )

    def test_normal_scenario_has_no_route_delay(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"normal": 1},
                products=config().products,
            )
        )
        shipment = dataset.shipments[0]
        self.assertLessEqual(shipment.actual_departure, shipment.planned_departure + timedelta(hours=1))


if __name__ == "__main__":
    unittest.main()
