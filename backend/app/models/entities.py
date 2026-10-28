from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from backend.app.core.time import to_utc
from backend.app.models.base import Base, UTCDateTime
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


def enum_column(enum_type: type[object]) -> SqlEnum:
    return SqlEnum(
        enum_type,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    shipments: Mapped[list[Shipment]] = relationship(back_populates="product")
    threshold_policies: Mapped[list[ThresholdPolicy]] = relationship(
        back_populates="product"
    )


class ThresholdPolicy(Base):
    __tablename__ = "threshold_policies"
    __table_args__ = (
        CheckConstraint("min_temp_c <= max_temp_c", name="ck_policy_temp_range"),
        CheckConstraint(
            "(min_humidity_pct IS NULL AND max_humidity_pct IS NULL) OR "
            "(min_humidity_pct IS NOT NULL AND max_humidity_pct IS NOT NULL)",
            name="ck_policy_humidity_pair",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_policy_effective_range",
        ),
        CheckConstraint("max_excursion_minutes >= 0", name="ck_policy_duration"),
        UniqueConstraint("product_id", "version", name="uq_policy_product_version"),
    )

    policy_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id"), nullable=False, index=True
    )
    min_temp_c: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    max_temp_c: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    max_excursion_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    min_humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    max_humidity_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    effective_from: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(UTCDateTime())
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    product: Mapped[Product] = relationship(back_populates="threshold_policies")
    excursions: Mapped[list[Excursion]] = relationship(back_populates="policy")

    @validates("effective_from", "effective_to")
    def validate_policy_datetime(
        self, key: str, value: datetime | None
    ) -> datetime | None:
        return None if value is None else to_utc(value)


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (
        CheckConstraint(
            "planned_delivery >= planned_departure",
            name="ck_shipment_planned_order",
        ),
        CheckConstraint(
            "actual_delivery IS NULL OR actual_departure IS NULL OR "
            "actual_delivery >= actual_departure OR "
            "issue_type = 'delivery_before_departure'",
            name="ck_shipment_actual_order",
        ),
        Index("ix_shipments_status", "status"),
    )

    shipment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.product_id"), nullable=False, index=True
    )
    origin: Mapped[str] = mapped_column(String(200), nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_departure: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    planned_delivery: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    actual_departure: Mapped[datetime | None] = mapped_column(UTCDateTime())
    actual_delivery: Mapped[datetime | None] = mapped_column(UTCDateTime())
    issue_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[ShipmentStatus] = mapped_column(
        enum_column(ShipmentStatus), nullable=False
    )

    product: Mapped[Product] = relationship(back_populates="shipments")
    assignments: Mapped[list[ContainerAssignment]] = relationship(
        back_populates="shipment"
    )
    route_stops: Mapped[list[RouteStop]] = relationship(back_populates="shipment")
    excursions: Mapped[list[Excursion]] = relationship(back_populates="shipment")
    custody_events: Mapped[list[CustodyEvent]] = relationship(back_populates="shipment")

    @validates("planned_departure", "planned_delivery", "actual_departure", "actual_delivery")
    def validate_shipment_datetime(
        self, key: str, value: datetime | None
    ) -> datetime | None:
        return None if value is None else to_utc(value)


class Container(Base):
    __tablename__ = "containers"

    container_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    container_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ContainerStatus] = mapped_column(
        enum_column(ContainerStatus), nullable=False
    )

    assignments: Mapped[list[ContainerAssignment]] = relationship(
        back_populates="container"
    )
    sensors: Mapped[list[Sensor]] = relationship(back_populates="container")


class ContainerAssignment(Base):
    __tablename__ = "container_assignments"
    __table_args__ = (
        CheckConstraint(
            "assigned_to IS NULL OR assigned_to > assigned_from",
            name="ck_assignment_interval",
        ),
        UniqueConstraint(
            "assignment_id", "container_id", name="uq_assignment_container"
        ),
        Index("ix_assignments_shipment", "shipment_id"),
        Index("ix_assignments_container_time", "container_id", "assigned_from"),
    )

    assignment_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    container_id: Mapped[str] = mapped_column(
        ForeignKey("containers.container_id"), nullable=False
    )
    shipment_id: Mapped[str] = mapped_column(
        ForeignKey("shipments.shipment_id"), nullable=False
    )
    assigned_from: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    assigned_to: Mapped[datetime | None] = mapped_column(UTCDateTime())

    container: Mapped[Container] = relationship(back_populates="assignments")
    shipment: Mapped[Shipment] = relationship(back_populates="assignments")
    readings: Mapped[list[SensorReading]] = relationship(
        back_populates="assignment"
    )
    excursions: Mapped[list[Excursion]] = relationship(
        back_populates="assignment"
    )

    @validates("assigned_from", "assigned_to")
    def validate_assignment_datetime(
        self, key: str, value: datetime | None
    ) -> datetime | None:
        return None if value is None else to_utc(value)


class Sensor(Base):
    __tablename__ = "sensors"
    __table_args__ = (
        CheckConstraint(
            "calibration_due_at > calibrated_at",
            name="ck_sensor_calibration_order",
        ),
        UniqueConstraint("sensor_id", "container_id", name="uq_sensor_container"),
        Index("ix_sensors_status", "status"),
    )

    sensor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    container_id: Mapped[str] = mapped_column(
        ForeignKey("containers.container_id"), nullable=False, index=True
    )
    sensor_type: Mapped[SensorType] = mapped_column(
        enum_column(SensorType), nullable=False
    )
    calibrated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    calibration_due_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False
    )
    status: Mapped[SensorStatus] = mapped_column(
        enum_column(SensorStatus), nullable=False
    )

    container: Mapped[Container] = relationship(back_populates="sensors")
    readings: Mapped[list[SensorReading]] = relationship(
        back_populates="sensor", overlaps="assignment,readings"
    )
    excursions: Mapped[list[Excursion]] = relationship(
        back_populates="sensor", overlaps="assignment,excursions"
    )

    @validates("calibrated_at", "calibration_due_at")
    def validate_sensor_datetime(self, key: str, value: datetime) -> datetime:
        return to_utc(value)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "container_id"],
            [
                "container_assignments.assignment_id",
                "container_assignments.container_id",
            ],
            name="fk_reading_assignment_container",
        ),
        ForeignKeyConstraint(
            ["sensor_id", "container_id"],
            ["sensors.sensor_id", "sensors.container_id"],
            name="fk_reading_sensor_container",
        ),
        UniqueConstraint("sensor_id", "recorded_at", name="uq_reading_sensor_time"),
        Index("ix_readings_recorded_at", "recorded_at"),
    )

    reading_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(32), nullable=False)
    container_id: Mapped[str] = mapped_column(String(32), nullable=False)
    sensor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    quality_status: Mapped[ReadingQualityStatus] = mapped_column(
        enum_column(ReadingQualityStatus), nullable=False
    )
    issue_type: Mapped[str | None] = mapped_column(String(100))

    sensor: Mapped[Sensor] = relationship(
        back_populates="readings", overlaps="assignment,readings"
    )
    assignment: Mapped[ContainerAssignment] = relationship(
        back_populates="readings", overlaps="sensor,readings"
    )

    @validates("recorded_at")
    def validate_reading_datetime(self, key: str, value: datetime) -> datetime:
        return to_utc(value)


class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = (
        UniqueConstraint(
            "shipment_id", "sequence_number", name="uq_route_stop_sequence"
        ),
        CheckConstraint("sequence_number > 0", name="ck_route_stop_sequence"),
        CheckConstraint(
            "actual_departure IS NULL OR actual_arrival IS NULL OR "
            "actual_departure >= actual_arrival",
            name="ck_route_stop_actual_order",
        ),
        Index("ix_route_stops_shipment", "shipment_id"),
    )

    route_stop_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(
        ForeignKey("shipments.shipment_id"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_arrival: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    actual_arrival: Mapped[datetime | None] = mapped_column(UTCDateTime())
    actual_departure: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[RouteStopStatus] = mapped_column(
        enum_column(RouteStopStatus), nullable=False
    )

    shipment: Mapped[Shipment] = relationship(back_populates="route_stops")

    @validates("planned_arrival", "actual_arrival", "actual_departure")
    def validate_route_datetime(
        self, key: str, value: datetime | None
    ) -> datetime | None:
        return None if value is None else to_utc(value)


class Excursion(Base):
    __tablename__ = "excursions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "container_id"],
            [
                "container_assignments.assignment_id",
                "container_assignments.container_id",
            ],
            name="fk_excursion_assignment_container",
        ),
        ForeignKeyConstraint(
            ["sensor_id", "container_id"],
            ["sensors.sensor_id", "sensors.container_id"],
            name="fk_excursion_sensor_container",
        ),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 0",
            name="ck_excursion_duration",
        ),
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_excursion_time_order",
        ),
        Index("ix_excursions_status_severity", "status", "severity"),
    )

    excursion_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(32), nullable=False)
    container_id: Mapped[str] = mapped_column(String(32), nullable=False)
    shipment_id: Mapped[str] = mapped_column(
        ForeignKey("shipments.shipment_id"), nullable=False, index=True
    )
    sensor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("threshold_policies.policy_id"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[ExcursionSeverity] = mapped_column(
        enum_column(ExcursionSeverity), nullable=False
    )
    status: Mapped[ExcursionStatus] = mapped_column(
        enum_column(ExcursionStatus), nullable=False
    )
    decision_reason: Mapped[str] = mapped_column(String(500), nullable=False)

    shipment: Mapped[Shipment] = relationship(back_populates="excursions")
    sensor: Mapped[Sensor] = relationship(
        back_populates="excursions", overlaps="assignment,excursions"
    )
    assignment: Mapped[ContainerAssignment] = relationship(
        back_populates="excursions", overlaps="sensor,excursions"
    )
    policy: Mapped[ThresholdPolicy] = relationship(back_populates="excursions")
    corrective_actions: Mapped[list[CorrectiveAction]] = relationship(
        back_populates="excursion"
    )
    evidence_links: Mapped[list[ExcursionEvidence]] = relationship(
        back_populates="excursion", cascade="all, delete-orphan"
    )

    @validates("started_at", "ended_at")
    def validate_excursion_datetime(
        self, key: str, value: datetime | None
    ) -> datetime | None:
        return None if value is None else to_utc(value)


class ExcursionEvidence(Base):
    __tablename__ = "excursion_evidence"
    __table_args__ = (
        UniqueConstraint(
            "excursion_id", "reading_id", name="uq_excursion_evidence_reading"
        ),
        Index("ix_excursion_evidence_reading", "reading_id"),
    )

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    excursion_id: Mapped[str] = mapped_column(
        ForeignKey("excursions.excursion_id"), nullable=False, index=True
    )
    reading_id: Mapped[str] = mapped_column(
        ForeignKey("sensor_readings.reading_id"), nullable=False, index=True
    )

    excursion: Mapped[Excursion] = relationship(back_populates="evidence_links")
    reading: Mapped[SensorReading] = relationship()


class CustodyEvent(Base):
    __tablename__ = "custody_events"
    __table_args__ = (Index("ix_custody_events_time", "event_time"),)

    custody_event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    shipment_id: Mapped[str] = mapped_column(
        ForeignKey("shipments.shipment_id"), nullable=False, index=True
    )
    event_time: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    event_type: Mapped[CustodyEventType] = mapped_column(
        enum_column(CustodyEventType), nullable=False
    )
    from_party: Mapped[str | None] = mapped_column(String(200))
    to_party: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_ref: Mapped[str | None] = mapped_column(String(500))

    shipment: Mapped[Shipment] = relationship(back_populates="custody_events")

    @validates("event_time")
    def validate_event_datetime(self, key: str, value: datetime) -> datetime:
        return to_utc(value)


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"
    __table_args__ = (
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_action_completion_order",
        ),
        Index("ix_actions_status", "status"),
    )

    action_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    excursion_id: Mapped[str] = mapped_column(
        ForeignKey("excursions.excursion_id"), nullable=False, index=True
    )
    assigned_to: Mapped[str] = mapped_column(String(200), nullable=False)
    action_type: Mapped[CorrectiveActionType] = mapped_column(
        enum_column(CorrectiveActionType), nullable=False
    )
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[CorrectiveActionStatus] = mapped_column(
        enum_column(CorrectiveActionStatus), nullable=False
    )
    outcome: Mapped[str | None] = mapped_column(String(1000))

    excursion: Mapped[Excursion] = relationship(back_populates="corrective_actions")

    @validates("created_at", "completed_at")
    def validate_action_datetime(
        self, key: str, value: datetime | None
    ) -> datetime | None:
        return None if value is None else to_utc(value)
