import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from backend.app.db.database import create_schema, persist_dataset
from backend.app.services.detection import DetectorConfig
from backend.app.services.generator import (
    GeneratorConfig,
    ProductSpec,
    generate_dataset,
)
from backend.app.services.monitoring import (
    detect_persisted_dataset,
    load_operational_dataset,
)


class MonitoringIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_url = "sqlite:///" + str(Path(self.temp_dir.name) / "monitoring.sqlite")
        self.engine = create_schema(self.database_url)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()

    @staticmethod
    def _dataset():
        return generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"brief_excursion": 1},
                products=(
                    ProductSpec(
                        "Monitoring fixture",
                        "cold_chain",
                        Decimal("2"),
                        Decimal("8"),
                        30,
                    ),
                ),
            )
        )

    def test_detects_against_persisted_operational_records(self) -> None:
        dataset = self._dataset()
        persist_dataset(dataset, self.session_factory)
        session = self.session_factory()
        try:
            report = detect_persisted_dataset(
                session,
                config=DetectorConfig(sampling_interval_minutes=5),
            )
            excursion_findings = [
                finding
                for finding in report.findings
                if finding.finding_type == "threshold_excursion"
            ]
            self.assertTrue(excursion_findings)
            self.assertEqual(excursion_findings[0].shipment_id, dataset.shipments[0].shipment_id)
            self.assertEqual(excursion_findings[0].sensor_id, dataset.excursions[0].sensor_id)
            self.assertEqual(excursion_findings[0].policy_id, dataset.policies[0].policy_id)
        finally:
            session.close()

    def test_loaded_dataset_contains_operational_records_only(self) -> None:
        dataset = self._dataset()
        persist_dataset(dataset, self.session_factory)
        session = self.session_factory()
        try:
            loaded = load_operational_dataset(session)
            self.assertEqual(len(loaded.shipments), 1)
            self.assertEqual(len(loaded.excursion_evidence), len(dataset.excursion_evidence))
            self.assertEqual(loaded.ground_truth, [])
            self.assertIsNone(loaded.config)
        finally:
            session.close()

    def test_scoped_loading_by_shipment_ids(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=2,
                container_count=2,
                scenario_counts={"brief_excursion": 1, "normal": 1},
                products=(
                    ProductSpec(
                        "Monitoring fixture",
                        "cold_chain",
                        Decimal("2"),
                        Decimal("8"),
                        30,
                    ),
                ),
            )
        )
        persist_dataset(dataset, self.session_factory)
        session = self.session_factory()
        try:
            target_id = dataset.shipments[0].shipment_id
            loaded = load_operational_dataset(session, shipment_ids=[target_id])
            self.assertEqual(len(loaded.shipments), 1)
            self.assertEqual(loaded.shipments[0].shipment_id, target_id)
            report = detect_persisted_dataset(session, shipment_ids=[target_id])
            self.assertTrue(all(f.shipment_id == target_id for f in report.findings if f.shipment_id))
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
