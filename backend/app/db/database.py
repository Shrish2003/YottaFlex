from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import create_engine, event, insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.base import Base
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
from backend.app.services.generator import GeneratedDataset


def create_engine_for_url(database_url: str) -> Engine:
    if not database_url.strip():
        raise ValueError("database_url must not be empty")
    engine = create_engine(database_url, future=True)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys=ON")
    return engine


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine_for_url(database_url)
    factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    factory.engine = engine
    return factory


def create_schema(database_url: str) -> Engine:
    engine = create_engine_for_url(database_url)
    Base.metadata.create_all(engine)
    return engine


def persist_dataset_orm(
    dataset: GeneratedDataset, session_factory: Callable[[], Session]
) -> None:
    session = session_factory()
    try:
        for collection in dataset.operational_collections():
            session.add_all(collection)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def persist_dataset(
    dataset: GeneratedDataset, session_factory: Callable[[], Session]
) -> None:
    collections = (
        (Product, dataset.products),
        (ThresholdPolicy, dataset.policies),
        (Shipment, dataset.shipments),
        (Container, dataset.containers),
        (ContainerAssignment, dataset.assignments),
        (Sensor, dataset.sensors),
        (SensorReading, dataset.readings),
        (RouteStop, dataset.route_stops),
        (Excursion, dataset.excursions),
        (ExcursionEvidence, dataset.excursion_evidence),
        (CustodyEvent, dataset.custody_events),
        (CorrectiveAction, dataset.corrective_actions),
    )
    session = session_factory()
    try:
        for model, records in collections:
            if records:
                session.execute(insert(model), [_column_mapping(record, model) for record in records])
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _column_mapping(record: object, model: type[Base]) -> dict[str, object]:
    values: dict[str, object] = {}
    for column in model.__table__.columns:
        value = getattr(record, column.name)
        if value is None and column.name.endswith("_id"):
            relationship = getattr(record, column.name[:-3], None)
            if relationship is not None:
                value = getattr(relationship, column.name)
        values[column.name] = value
    return values
