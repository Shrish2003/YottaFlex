import unittest
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.entities import (
    Base,
    Container,
    ContainerAssignment,
    CorrectiveAction,
    CustodyEvent,
    Excursion,
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


UTC = timezone.utc
START = datetime(2026, 1, 1, 8, tzinfo=UTC)
END = datetime(2026, 1, 3, 8, tzinfo=UTC)


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(cls.engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(cls.engine)

    def setUp(self) -> None:
        self.session = Session(self.engine)
        self.product = Product(
            product_id="PRD-000001",
            name="Test product",
            category="cold_chain",
            active=True,
        )
        self.policy = ThresholdPolicy(
            policy_id="POL-000001",
            product=self.product,
            min_temp_c=Decimal("2.000"),
            max_temp_c=Decimal("8.000"),
            max_excursion_minutes=30,
            effective_from=START,
            version=1,
        )
        self.shipment = Shipment(
            shipment_id="SHP-2026-000001",
            product=self.product,
            origin="Origin",
            destination="Destination",
            planned_departure=START,
            planned_delivery=END,
            status=ShipmentStatus.PLANNED,
        )
        self.container = Container(
            container_id="CNT-000001",
            container_type="validated",
            status=ContainerStatus.PREPARED,
        )
        self.assignment = ContainerAssignment(
            assignment_id="ASN-2026-000001",
            container=self.container,
            shipment=self.shipment,
            assigned_from=START,
            assigned_to=END,
        )
        self.sensor = Sensor(
            sensor_id="SNS-CNT-000001-TEMP",
            container=self.container,
            sensor_type=SensorType.TEMPERATURE,
            calibrated_at=START,
            calibration_due_at=END,
            status=SensorStatus.ACTIVE,
        )

    def tearDown(self) -> None:
        self.session.rollback()
        self.session.close()

    def test_core_relationships_persist(self) -> None:
        reading = SensorReading(
            reading_id="RDG-SNS-CNT-000001-TEMP-20260101T080000Z",
            assignment=self.assignment,
            container_id=self.container.container_id,
            sensor=self.sensor,
            recorded_at=START,
            value=Decimal("5.2500"),
            unit="°C",
            quality_status=ReadingQualityStatus.VALID,
        )
        stop = RouteStop(
            route_stop_id="RST-000001",
            shipment=self.shipment,
            sequence_number=1,
            location="Hub",
            planned_arrival=START,
            status=RouteStopStatus.PLANNED,
        )
        excursion = Excursion(
            excursion_id="EXC-2026-000001",
            assignment=self.assignment,
            container_id=self.container.container_id,
            shipment=self.shipment,
            sensor=self.sensor,
            policy=self.policy,
            started_at=START,
            severity=ExcursionSeverity.WARNING,
            status=ExcursionStatus.OPEN,
            decision_reason="Recorded violation",
        )
        action = CorrectiveAction(
            action_id="ACT-000001",
            excursion=excursion,
            assigned_to="quality",
            action_type=CorrectiveActionType.REVIEW,
            description="Review evidence",
            created_at=START,
            status=CorrectiveActionStatus.OPEN,
        )
        custody = CustodyEvent(
            custody_event_id="CUS-000001",
            shipment=self.shipment,
            event_time=START,
            event_type=CustodyEventType.DISPATCHED,
            to_party="carrier",
            location="Origin",
        )
        self.session.add_all(
            [self.product, self.assignment, reading, stop, excursion, action, custody]
        )
        self.session.commit()

        loaded = self.session.get(Shipment, self.shipment.shipment_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded.assignments), 1)
        self.assertEqual(len(loaded.route_stops), 1)
        self.assertEqual(len(loaded.excursions), 1)
        self.assertEqual(len(loaded.custody_events), 1)
        self.assertEqual(
            loaded.assignments[0].container.sensors[0].readings[0].value,
            Decimal("5.2500"),
        )
        self.assertEqual(loaded.excursions[0].corrective_actions[0].action_id, "ACT-000001")

    def test_duplicate_reading_timestamp_is_rejected(self) -> None:
        first = SensorReading(
            reading_id="RDG-1",
            assignment=self.assignment,
            container_id=self.container.container_id,
            sensor=self.sensor,
            recorded_at=START,
            value=Decimal("5"),
            unit="°C",
            quality_status=ReadingQualityStatus.VALID,
        )
        duplicate = SensorReading(
            reading_id="RDG-2",
            assignment=self.assignment,
            container_id=self.container.container_id,
            sensor=self.sensor,
            recorded_at=START,
            value=Decimal("6"),
            unit="°C",
            quality_status=ReadingQualityStatus.VALID,
        )
        self.session.add_all([self.product, first, duplicate])
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_invalid_foreign_key_is_rejected(self) -> None:
        self.session.add(
            ContainerAssignment(
                assignment_id="ASN-INVALID",
                container=self.container,
                shipment_id="SHP-MISSING",
                assigned_from=START,
                assigned_to=END,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_policy_constraints_reject_invalid_values(self) -> None:
        self.session.add(self.product)
        self.session.add(
            ThresholdPolicy(
                policy_id="POL-INVALID",
                product=self.product,
                min_temp_c=Decimal("9"),
                max_temp_c=Decimal("8"),
                max_excursion_minutes=-1,
                min_humidity_pct=Decimal("30"),
                effective_from=START,
                effective_to=START,
                version=1,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_lifecycle_constraints_reject_invalid_dates(self) -> None:
        self.session.add(self.product)
        self.session.add(
            Shipment(
                shipment_id="SHP-INVALID",
                product=self.product,
                origin="Origin",
                destination="Destination",
                planned_departure=END,
                planned_delivery=START,
                status=ShipmentStatus.PLANNED,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_unlabeled_delivery_before_departure_is_rejected(self) -> None:
        self.session.add(self.product)
        self.session.add(
            Shipment(
                shipment_id="SHP-INVALID-ACTUAL",
                product=self.product,
                origin="Origin",
                destination="Destination",
                planned_departure=START,
                planned_delivery=END,
                actual_departure=END,
                actual_delivery=START,
                status=ShipmentStatus.DELIVERED,
            )
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_naive_model_datetime_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Sensor(
                sensor_id="SNS-NAIVE",
                container=self.container,
                sensor_type=SensorType.TEMPERATURE,
                calibrated_at=datetime(2026, 1, 1, 8),
                calibration_due_at=END,
                status=SensorStatus.ACTIVE,
            )

    def test_enum_values_are_validated(self) -> None:
        self.session.add(self.product)
        self.session.add(
            Shipment(
                shipment_id="SHP-INVALID-STATUS",
                product=self.product,
                origin="Origin",
                destination="Destination",
                planned_departure=START,
                planned_delivery=END,
                status="unknown",
            )
        )
        with self.assertRaises((ValueError, IntegrityError)):
            self.session.commit()


if __name__ == "__main__":
    unittest.main()
