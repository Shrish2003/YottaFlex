from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

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
from backend.app.services.detection import (
    DetectionReport,
    DetectorConfig,
    detect_dataset,
)
from backend.app.services.generator import GeneratedDataset


def detect_persisted_dataset(
    session: Session,
    *,
    config: DetectorConfig | None = None,
    shipment_ids: Iterable[str] | None = None,
) -> DetectionReport:
    """Run detection against operational records already persisted in a session."""

    if not isinstance(session, Session):
        raise TypeError("session must be a SQLAlchemy Session")
    dataset = load_operational_dataset(session, shipment_ids=shipment_ids)
    return detect_dataset(dataset, config=config)


def load_operational_dataset(
    session: Session,
    *,
    shipment_ids: Iterable[str] | None = None,
) -> GeneratedDataset:
    """Load detector inputs without loading ground-truth records."""

    if not isinstance(session, Session):
        raise TypeError("session must be a SQLAlchemy Session")

    if shipment_ids is not None:
        target_ids = list(shipment_ids)
        if not target_ids:
            return GeneratedDataset()
        shipments = list(
            session.scalars(
                select(Shipment).where(Shipment.shipment_id.in_(target_ids))
            ).all()
        )
        assignments = list(
            session.scalars(
                select(ContainerAssignment).where(
                    ContainerAssignment.shipment_id.in_(target_ids)
                )
            ).all()
        )
        container_ids = {a.container_id for a in assignments}
        assignment_ids = {a.assignment_id for a in assignments}
        containers = (
            list(
                session.scalars(
                    select(Container).where(Container.container_id.in_(container_ids))
                ).all()
            )
            if container_ids
            else []
        )
        sensors = (
            list(
                session.scalars(
                    select(Sensor).where(Sensor.container_id.in_(container_ids))
                ).all()
            )
            if container_ids
            else []
        )
        min_time = min(a.assigned_from for a in assignments)
        max_time = max(a.assigned_to for a in assignments)
        readings = (
            list(
                session.scalars(
                    select(SensorReading).where(
                        SensorReading.assignment_id.in_(assignment_ids),
                        SensorReading.recorded_at >= min_time,
                        SensorReading.recorded_at <= max_time,
                    )
                ).all()
            )
            if assignment_ids
            else []
        )
        route_stops = list(
            session.scalars(
                select(RouteStop).where(RouteStop.shipment_id.in_(target_ids))
            ).all()
        )
        excursions = list(
            session.scalars(
                select(Excursion).where(Excursion.shipment_id.in_(target_ids))
            ).all()
        )
        excursion_ids = {e.excursion_id for e in excursions}
        excursion_evidence = (
            list(
                session.scalars(
                    select(ExcursionEvidence).where(
                        ExcursionEvidence.excursion_id.in_(excursion_ids)
                    )
                ).all()
            )
            if excursion_ids
            else []
        )
        custody_events = list(
            session.scalars(
                select(CustodyEvent).where(CustodyEvent.shipment_id.in_(target_ids))
            ).all()
        )
        corrective_actions = (
            list(
                session.scalars(
                    select(CorrectiveAction).where(
                        CorrectiveAction.excursion_id.in_(excursion_ids)
                    )
                ).all()
            )
            if excursion_ids
            else []
        )
        products = list(session.scalars(select(Product)).all())
        policies = list(session.scalars(select(ThresholdPolicy)).all())
        return GeneratedDataset(
            products=products,
            policies=policies,
            shipments=shipments,
            containers=containers,
            assignments=assignments,
            sensors=sensors,
            readings=readings,
            route_stops=route_stops,
            excursions=excursions,
            excursion_evidence=excursion_evidence,
            custody_events=custody_events,
            corrective_actions=corrective_actions,
        )

    return GeneratedDataset(
        products=_all(session, Product),
        policies=_all(session, ThresholdPolicy),
        shipments=_all(session, Shipment),
        containers=_all(session, Container),
        assignments=_all(session, ContainerAssignment),
        sensors=_all(session, Sensor),
        readings=_all(session, SensorReading),
        route_stops=_all(session, RouteStop),
        excursions=_all(session, Excursion),
        excursion_evidence=_all(session, ExcursionEvidence),
        custody_events=_all(session, CustodyEvent),
        corrective_actions=_all(session, CorrectiveAction),
    )


def _all(session: Session, model: type[object]) -> list[object]:
    return list(session.scalars(select(model)).all())
