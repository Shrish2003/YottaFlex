import os
import unittest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import create_engine_for_url, persist_dataset
from backend.app.models.base import Base
from backend.app.models.entities import (
    Container,
    ContainerAssignment,
    Excursion,
    ExcursionEvidence,
    Sensor,
    SensorReading,
    Shipment,
)
from backend.app.services.generator import (
    GeneratorConfig,
    ProductSpec,
    generate_dataset,
)
from backend.app.services.validation import validate_dataset


POSTGRESQL_URL = os.environ.get("DATABASE_URL", "")


@unittest.skipUnless(
    POSTGRESQL_URL.startswith("postgresql"),
    "DATABASE_URL must reference PostgreSQL to run integration tests",
)
class PostgreSQLIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = f"yottaflex_test_{uuid4().hex}"
        self.admin_engine = create_engine_for_url(POSTGRESQL_URL)
        with self.admin_engine.begin() as connection:
            connection.execute(text(f"CREATE SCHEMA {self.schema}"))
        self.admin_engine.dispose()

        self.engine = create_engine(
            POSTGRESQL_URL,
            connect_args={"options": f"-csearch_path={self.schema}"},
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def tearDown(self) -> None:
        self.engine.dispose()
        admin_engine = create_engine_for_url(POSTGRESQL_URL)
        try:
            with admin_engine.begin() as connection:
                connection.execute(text(f"DROP SCHEMA {self.schema} CASCADE"))
        finally:
            admin_engine.dispose()

    @staticmethod
    def _fixture():
        config = GeneratorConfig(
            shipment_count=1,
            container_count=1,
            scenario_counts={"brief_excursion": 1},
            products=(
                ProductSpec(
                    "PostgreSQL Smoke",
                    "cold_chain",
                    Decimal("2"),
                    Decimal("8"),
                    30,
                ),
            ),
        )
        dataset = generate_dataset(config)
        report = validate_dataset(dataset, require_scenario_coverage=False)
        if not report.passed:
            raise AssertionError(report.errors)
        return dataset

    def test_persistence_round_trip_and_evidence_context(self) -> None:
        dataset = self._fixture()
        persist_dataset(dataset, self.session_factory)

        session = self.session_factory()
        try:
            expected_counts = {
                Shipment: len(dataset.shipments),
                Container: len(dataset.containers),
                ContainerAssignment: len(dataset.assignments),
                Sensor: len(dataset.sensors),
                SensorReading: len(dataset.readings),
                Excursion: len(dataset.excursions),
                ExcursionEvidence: len(dataset.excursion_evidence),
            }
            for model, expected in expected_counts.items():
                actual = session.scalar(select(func.count()).select_from(model))
                self.assertEqual(actual, expected, model.__name__)

            shipment = session.scalars(select(Shipment)).one()
            assignment = session.scalars(select(ContainerAssignment)).one()
            excursion = session.scalars(select(Excursion)).one()
            evidence_rows = session.scalars(
                select(ExcursionEvidence).order_by(ExcursionEvidence.evidence_id)
            ).all()

            self.assertEqual(assignment.shipment.shipment_id, shipment.shipment_id)
            self.assertEqual(assignment.container.container_id, shipment.assignments[0].container_id)
            self.assertEqual(excursion.assignment.assignment_id, assignment.assignment_id)
            self.assertEqual(excursion.sensor.container_id, assignment.container_id)
            self.assertEqual(len(evidence_rows), len(dataset.excursion_evidence))
            self.assertGreater(len(evidence_rows), 1)
            for evidence in evidence_rows:
                reading = session.get(SensorReading, evidence.reading_id)
                if reading is None:
                    self.fail(
                        f"persisted evidence {evidence.evidence_id} "
                        "references a missing reading"
                    )
                self.assertEqual(evidence.excursion_id, excursion.excursion_id)
                self.assertEqual(evidence.reading.reading_id, reading.reading_id)
                self.assertEqual(reading.assignment.assignment_id, assignment.assignment_id)
                self.assertEqual(reading.sensor.container_id, assignment.container_id)
                self.assertEqual(reading.assignment_id, excursion.assignment_id)
                self.assertEqual(reading.container_id, excursion.container_id)
                self.assertEqual(reading.sensor_id, excursion.sensor_id)
        finally:
            session.close()

    def test_failed_persistence_rolls_back_transaction(self) -> None:
        dataset = self._fixture()
        dataset.assignments[0].shipment_id = "SHP-MISSING"

        with self.assertRaises(IntegrityError):
            persist_dataset(dataset, self.session_factory)

        session = self.session_factory()
        try:
            self.assertEqual(session.scalar(select(func.count()).select_from(Shipment)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(Container)), 0)
            self.assertEqual(session.scalar(select(func.count()).select_from(SensorReading)), 0)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
