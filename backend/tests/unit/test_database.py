import unittest
from decimal import Decimal
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import create_engine_for_url, create_schema, persist_dataset
from backend.app.models.entities import (
    Excursion,
    ExcursionEvidence,
    Product,
    Shipment,
    ThresholdPolicy,
)
from backend.app.services.generator import (
    GeneratorConfig,
    ProductSpec,
    SCENARIO_TYPES,
    generate_dataset,
)
from backend.app.services.validation import validate_dataset
from backend.app.services.export import export_dataset


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_url = "sqlite:///" + str(Path(self.temp_dir.name) / "test.sqlite")
        self.engine = create_schema(self.database_url)
        self.persistence_engine = create_engine_for_url(self.database_url)
        self.session_factory = sessionmaker(
            bind=self.persistence_engine,
            expire_on_commit=False,
        )

    def tearDown(self) -> None:
        self.engine.dispose()
        self.persistence_engine.dispose()
        self.temp_dir.cleanup()

    def test_persistence_round_trip_uses_foreign_keys(self) -> None:
        config = GeneratorConfig(
            shipment_count=1,
            container_count=1,
            scenario_counts={"normal": 1},
            products=(ProductSpec("Smoke", "cold_chain", Decimal("2"), Decimal("8"), 30),),
        )
        dataset = generate_dataset(config)
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertTrue(report.passed, report.errors)
        persist_dataset(dataset, self.session_factory)
        session = self.session_factory()
        try:
            self.assertEqual(len(session.scalars(select(Product)).all()), 1)
            self.assertEqual(len(session.scalars(select(Shipment)).all()), 1)
        finally:
            session.close()

    def test_failed_persistence_rolls_back(self) -> None:
        config = GeneratorConfig(
            shipment_count=1,
            container_count=1,
            scenario_counts={"normal": 1},
            products=(ProductSpec("Smoke", "cold_chain", Decimal("2"), Decimal("8"), 30),),
        )
        dataset = generate_dataset(config)
        dataset.assignments[0].shipment = None
        dataset.assignments[0].shipment_id = "SHP-MISSING"
        with self.assertRaises(Exception):
            persist_dataset(dataset, self.session_factory)
        session = self.session_factory()
        try:
            self.assertEqual(session.scalars(select(Product)).all(), [])
        finally:
            session.close()

    def test_delivery_before_departure_anomaly_persists_and_remains_labeled(self) -> None:
        config = GeneratorConfig(
            shipment_count=1,
            container_count=1,
            scenario_counts={"delivery_before_departure": 1},
            products=(ProductSpec("Smoke", "cold_chain", Decimal("2"), Decimal("8"), 30),),
        )
        dataset = generate_dataset(config)
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertTrue(report.passed, report.errors)
        shipment = dataset.shipments[0]
        self.assertLess(shipment.actual_delivery, shipment.actual_departure)
        self.assertEqual(shipment.issue_type, "delivery_before_departure")

        persist_dataset(dataset, self.session_factory)
        with tempfile.TemporaryDirectory() as output_dir:
            export_dataset(dataset, report, output_dir)
            exported = Path(output_dir, "shipments.json").read_text(encoding="utf-8")
            self.assertIn("delivery_before_departure", exported)

        session = self.session_factory()
        try:
            persisted = session.scalars(select(Shipment)).one()
            self.assertLess(persisted.actual_delivery, persisted.actual_departure)
            self.assertEqual(persisted.issue_type, "delivery_before_departure")
        finally:
            session.close()

    def test_wrong_product_fixture_persists_alternate_policy_and_product(self) -> None:
        config = GeneratorConfig(
            shipment_count=1,
            container_count=1,
            scenario_counts={"wrong_product_threshold": 1},
            products=(ProductSpec("Smoke", "cold_chain", Decimal("2"), Decimal("8"), 30),),
        )
        dataset = generate_dataset(config)
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertTrue(report.passed, report.errors)
        persist_dataset(dataset, self.session_factory)

        session = self.session_factory()
        try:
            self.assertEqual(len(session.scalars(select(Product)).all()), 2)
            self.assertEqual(len(session.scalars(select(ThresholdPolicy)).all()), 2)
            excursion = session.scalars(select(Excursion)).one()
            evidence = session.scalars(select(ExcursionEvidence)).all()
            shipment = session.scalars(select(Shipment)).one()
            policy = session.get(ThresholdPolicy, excursion.policy_id)
            self.assertIsNotNone(policy)
            self.assertNotEqual(policy.product_id, shipment.product_id)
            self.assertTrue(evidence)
            self.assertEqual(evidence[0].excursion_id, excursion.excursion_id)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
