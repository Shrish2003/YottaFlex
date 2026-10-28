from __future__ import annotations

import os
import pickle
import threading
from collections.abc import Callable, Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.core.time import now_utc
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
    CorrectiveActionStatus,
    CorrectiveActionType,
    ExcursionSeverity,
    ExcursionStatus,
    ShipmentStatus,
)
from backend.app.services.actions import create_corrective_action
from backend.app.services.detection import DetectionFinding, detect_dataset
from backend.app.services.evaluation import evaluate_ground_truth
from backend.app.services.export import serialize_records
from backend.app.services.generator import (
    GeneratorConfig,
    GeneratedDataset,
    ProductSpec,
    generate_dataset,
)
from backend.app.services.monitoring import detect_persisted_dataset, load_operational_dataset
from backend.app.services.validation import ValidationReport, validate_dataset
from backend.app.db.database import persist_dataset


MAX_TELEMETRY_ITEMS = 500
MAX_EVIDENCE_ITEMS = 500
ALLOWED_EXPORT_DATASETS = {
    "products": Product,
    "threshold_policies": ThresholdPolicy,
    "shipments": Shipment,
    "containers": Container,
    "container_assignments": ContainerAssignment,
    "sensors": Sensor,
    "sensor_readings": SensorReading,
    "route_stops": RouteStop,
    "excursions": Excursion,
    "excursion_evidence": ExcursionEvidence,
    "custody_events": CustodyEvent,
    "corrective_actions": CorrectiveAction,
}
ALLOWED_EXPORT_FORMATS = {"csv", "json"}


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


class ProductSpecRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    min_temp_c: Decimal
    max_temp_c: Decimal
    max_excursion_minutes: int = Field(ge=0)
    min_humidity_pct: Decimal | None = None
    max_humidity_pct: Decimal | None = None


class GenerateRequest(BaseModel):
    seed: int = 20261022
    shipment_count: int = Field(gt=0)
    container_count: int = Field(gt=0)
    sampling_interval_minutes: int = Field(default=5, gt=0)
    min_trip_days: int = Field(default=2, gt=0)
    max_trip_days: int = Field(default=5, gt=0)
    scenario_counts: dict[str, int] = Field(min_length=1)
    products: list[ProductSpecRequest] = Field(min_length=1)
    start_datetime: datetime | None = None

    @model_validator(mode="after")
    def validate_scenario_counts(self) -> GenerateRequest:
        if self.start_datetime is not None and self.start_datetime.tzinfo is None:
            raise ValueError("start_datetime must be timezone-aware")
        if any(count < 0 for count in self.scenario_counts.values()):
            raise ValueError("scenario_counts must not contain negative values")
        if sum(self.scenario_counts.values()) != self.shipment_count:
            raise ValueError("scenario_counts must sum to shipment_count")
        if self.max_trip_days < self.min_trip_days:
            raise ValueError("max_trip_days must be greater than or equal to min_trip_days")
        return self


class GenerationResponse(BaseModel):
    run_id: str
    status: Literal["completed"]
    generated_at_utc: datetime
    seed: int
    counts: dict[str, int]
    validation_status: Literal["passed"]


class FindingResponse(BaseModel):
    finding_id: str
    finding_type: str
    reason: str
    shipment_id: str
    sensor_id: str | None = None
    assignment_id: str | None = None
    policy_id: str | None = None
    reading_ids: list[str] = Field(default_factory=list)
    excursion_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_minutes: int | None = None
    severity: str
    status: str


class SensorResponse(BaseModel):
    sensor_id: str
    sensor_type: str
    calibrated_at: datetime
    calibration_due_at: datetime
    status: str


class ContainerResponse(BaseModel):
    container_id: str
    container_type: str
    status: str
    assignment_id: str
    assigned_from: datetime
    assigned_to: datetime | None
    sensors: list[SensorResponse]


class RouteStopResponse(BaseModel):
    route_stop_id: str
    sequence_number: int
    location: str
    planned_arrival: datetime
    actual_arrival: datetime | None
    actual_departure: datetime | None
    status: str


class CustodyEventResponse(BaseModel):
    custody_event_id: str
    event_time: datetime
    event_type: str
    from_party: str | None
    to_party: str
    location: str
    evidence_ref: str | None


class ReadingResponse(BaseModel):
    reading_id: str
    sensor_id: str
    recorded_at: datetime
    value: Decimal
    unit: str
    quality_status: str
    issue_type: str | None


class ShipmentResponse(BaseModel):
    shipment_id: str
    product_id: str
    origin: str
    destination: str
    planned_departure: datetime
    planned_delivery: datetime
    actual_departure: datetime | None
    actual_delivery: datetime | None
    issue_type: str | None
    status: str
    detection_findings: list[FindingResponse] = Field(default_factory=list)
    containers: list[ContainerResponse] = Field(default_factory=list)
    route_stops: list[RouteStopResponse] = Field(default_factory=list)
    custody_events: list[CustodyEventResponse] = Field(default_factory=list)
    excursions: list[ExcursionResponse] = Field(default_factory=list)
    telemetry: list[ReadingResponse] = Field(default_factory=list)
    telemetry_truncated: bool = False


class ShipmentListResponse(BaseModel):
    items: list[ShipmentResponse]
    page: int
    page_size: int
    total: int


class ShipmentSummaryResponse(BaseModel):
    shipment_id: str
    reading_count: int
    telemetry_gap_count: int
    excursions_by_status: dict[str, int]
    excursions_by_severity: dict[str, int]
    open_corrective_action_count: int
    custody_event_count: int
    data_quality_status: Literal["passed", "warnings", "failed"]


class ExcursionResponse(BaseModel):
    excursion_id: str
    assignment_id: str
    container_id: str
    shipment_id: str
    sensor_id: str
    policy_id: str
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: int | None
    severity: str
    status: str
    decision_reason: str


class ExcursionListResponse(BaseModel):
    items: list[ExcursionResponse]
    page: int
    page_size: int
    total: int


class PolicyResponse(BaseModel):
    policy_id: str
    product_id: str
    version: int
    min_temp_c: Decimal
    max_temp_c: Decimal
    max_excursion_minutes: int
    min_humidity_pct: Decimal | None
    max_humidity_pct: Decimal | None
    effective_from: datetime
    effective_to: datetime | None


class EvidenceResponse(ReadingResponse):
    pass


class CorrectiveActionResponse(BaseModel):
    action_id: str
    excursion_id: str
    assigned_to: str
    action_type: str
    description: str
    created_at: datetime
    completed_at: datetime | None
    status: str
    outcome: str | None


class ExcursionDetailResponse(ExcursionResponse):
    policy: PolicyResponse
    sensor: SensorResponse
    evidence: list[EvidenceResponse]
    evidence_truncated: bool = False
    evidence_integrity_warnings: list[str] = Field(default_factory=list)
    data_gap_warnings: list[FindingResponse] = Field(default_factory=list)
    corrective_actions: list[CorrectiveActionResponse]
    detection_findings: list[FindingResponse]


class CorrectiveActionRequest(BaseModel):
    assigned_to: str = Field(min_length=1, max_length=200)
    action_type: CorrectiveActionType
    description: str = Field(min_length=1, max_length=1000)


class ValidationResponse(BaseModel):
    validation_status: Literal["passed", "failed"]
    errors: list[str]
    warnings: list[str]
    counts: dict[str, int]
    checks: list["ValidationCheckResponse"]


class ValidationCheckResponse(BaseModel):
    name: str
    status: Literal["passed", "warning", "failed"]
    count: int
    examples: list[str] = Field(default_factory=list)


class QualitySummaryResponse(BaseModel):
    from_timestamp: datetime | None
    to_timestamp: datetime | None
    shipments_total: int
    shipments_by_status: dict[str, int]
    excursions_by_status: dict[str, int]
    excursions_by_severity: dict[str, int]
    open_corrective_actions: int
    readings_total: int
    telemetry_gap_findings: int
    invalid_reading_findings: int
    calibration_failure_findings: int
    validation_status: Literal["passed", "warnings", "failed"]
    validation_errors: list[str]
    validation_warnings: list[str]
    validation_counts: dict[str, int]
    evaluation_metrics: dict[str, Any]


def create_app(session_factory: Callable[[], Session]) -> FastAPI:
    if not callable(session_factory):
        raise TypeError("session_factory must be callable")

    app = FastAPI(title="YottaFlex Cold-Chain Monitoring API", version="0.2.0")
    configured_origins = [
        origin.strip()
        for origin in os.environ.get(
            "YOTTAFLEX_ALLOWED_ORIGINS",
            "http://localhost:3000,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    origins = list(configured_origins)
    for o in configured_origins:
        if "localhost" in o:
            alt = o.replace("localhost", "127.0.0.1")
            if alt not in origins:
                origins.append(alt)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "Authorization"],
    )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exception: RequestValidationError) -> JSONResponse:
        details = [error["msg"] for error in exception.errors()]
        return _error_response(422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(HTTPException)
    async def handle_http_error(_: Request, exception: HTTPException) -> JSONResponse:
        detail = exception.detail
        if isinstance(detail, dict) and "error" in detail:
            return JSONResponse(status_code=exception.status_code, content=detail)
        return _error_response(
            exception.status_code,
            "BAD_REQUEST" if exception.status_code < 500 else "INTERNAL_ERROR",
            str(detail),
            [],
        )

    @app.post(
        "/api/generate",
        response_model=GenerationResponse,
        status_code=201,
        responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    )
    def generate(request: GenerateRequest) -> GenerationResponse:
        try:
            config = GeneratorConfig(
                seed=request.seed,
                shipment_count=request.shipment_count,
                container_count=request.container_count,
                sampling_interval_minutes=request.sampling_interval_minutes,
                min_trip_days=request.min_trip_days,
                max_trip_days=request.max_trip_days,
                scenario_counts=request.scenario_counts,
                products=tuple(
                    ProductSpec(
                        name=product.name,
                        category=product.category,
                        min_temp_c=product.min_temp_c,
                        max_temp_c=product.max_temp_c,
                        max_excursion_minutes=product.max_excursion_minutes,
                        min_humidity_pct=product.min_humidity_pct,
                        max_humidity_pct=product.max_humidity_pct,
                    )
                    for product in request.products
                ),
                start_datetime=request.start_datetime or GeneratorConfig.__dataclass_fields__["start_datetime"].default,
            )
            dataset = generate_dataset(config)
            report = validate_dataset(dataset, require_scenario_coverage=False)
            if not report.passed:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": {
                            "code": "DATASET_VALIDATION_FAILED",
                            "message": "Generated dataset failed validation",
                            "details": report.errors,
                        }
                    },
                )
            persist_dataset(dataset, session_factory)
        except IntegrityError as exception:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "GENERATION_CONFLICT",
                        "message": "Generation conflicts with existing persisted records; no records were replaced",
                        "details": [str(exception.orig)],
                    }
                },
            ) from exception
        except SQLAlchemyError as exception:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "code": "DATABASE_ERROR",
                        "message": "Dataset could not be persisted",
                        "details": [],
                    }
                },
            ) from exception
        run_id = f"GEN-{uuid4().hex[:12].upper()}"
        app.state.last_generation = {"run_id": run_id, "dataset": dataset, "report": report}
        return GenerationResponse(
            run_id=run_id,
            status="completed",
            generated_at_utc=now_utc(),
            seed=config.seed,
            counts=report.counts,
            validation_status="passed",
        )

    @app.get("/api/shipments", response_model=ShipmentListResponse)
    def list_shipments(
        status: str | None = None,
        product_id: str | None = None,
        origin: str | None = None,
        destination: str | None = None,
        from_timestamp: datetime | None = Query(default=None, alias="from"),
        to_timestamp: datetime | None = Query(default=None, alias="to"),
        sort: Literal["shipment_id", "planned_departure", "planned_delivery", "status"] = "shipment_id",
        order: Literal["asc", "desc"] = "asc",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=100),
    ) -> ShipmentListResponse:
        _validate_status(status, ShipmentStatus)
        _validate_time_window(from_timestamp, to_timestamp)
        with session_factory() as session:
            query = select(Shipment)
            query = _apply_shipment_filters(query, status, product_id, origin, destination, from_timestamp, to_timestamp)
            query = query.order_by(_sort_column(Shipment, sort, order))
            shipments = list(session.scalars(query).all())
            total = len(shipments)
            start = (page - 1) * page_size
            selected = shipments[start : start + page_size]
            findings = _findings_by_shipment(session, shipment_ids=[s.shipment_id for s in selected])
            return ShipmentListResponse(
                items=[_shipment_response(session, shipment, findings, include_telemetry=True) for shipment in selected],
                page=page,
                page_size=page_size,
                total=total,
            )

    @app.get("/api/shipments/{shipment_id}", response_model=ShipmentResponse)
    def get_shipment(shipment_id: str) -> ShipmentResponse:
        with session_factory() as session:
            shipment = session.get(Shipment, shipment_id)
            if shipment is None:
                raise _not_found("Shipment", shipment_id)
            findings = _findings_by_shipment(session, shipment_ids=[shipment_id])
            return _shipment_response(session, shipment, findings)

    @app.get("/api/shipments/{shipment_id}/summary", response_model=ShipmentSummaryResponse)
    def get_shipment_summary(shipment_id: str) -> ShipmentSummaryResponse:
        with session_factory() as session:
            shipment = session.get(Shipment, shipment_id)
            if shipment is None:
                raise _not_found("Shipment", shipment_id)
            findings = _findings_by_shipment(session, shipment_ids=[shipment_id]).get(shipment_id, [])
            excursions = list(session.scalars(select(Excursion).where(Excursion.shipment_id == shipment_id)).all())
            actions = list(
                session.scalars(
                    select(CorrectiveAction)
                    .join(Excursion)
                    .where(Excursion.shipment_id == shipment_id, CorrectiveAction.status.in_(
                        [CorrectiveActionStatus.OPEN, CorrectiveActionStatus.IN_PROGRESS]
                    ))
                ).all()
            )
            assignments = list(session.scalars(select(ContainerAssignment).where(ContainerAssignment.shipment_id == shipment_id)).all())
            readings = sum(
                session.scalar(
                    select(func.count()).select_from(SensorReading).where(
                        SensorReading.assignment_id == a.assignment_id,
                        SensorReading.recorded_at >= a.assigned_from,
                        SensorReading.recorded_at <= a.assigned_to,
                    )
                ) or 0
                for a in assignments
            )
            quality = _quality_state(findings)
            return ShipmentSummaryResponse(
                shipment_id=shipment_id,
                reading_count=readings,
                telemetry_gap_count=sum(item.get("finding_type") == "telemetry_gap" for item in findings),
                excursions_by_status=_enum_counts(excursions, "status"),
                excursions_by_severity=_enum_counts(excursions, "severity"),
                open_corrective_action_count=len(actions),
                custody_event_count=session.scalar(
                    select(func.count()).select_from(CustodyEvent).where(CustodyEvent.shipment_id == shipment_id)
                ) or 0,
                data_quality_status=quality,
            )

    @app.get("/api/excursions", response_model=ExcursionListResponse)
    def list_excursions(
        status: str | None = None,
        severity: str | None = None,
        shipment_id: str | None = None,
        sensor_id: str | None = None,
        sort: Literal["excursion_id", "started_at", "severity", "status"] = "excursion_id",
        order: Literal["asc", "desc"] = "asc",
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=100),
    ) -> ExcursionListResponse:
        _validate_status(status, ExcursionStatus)
        _validate_status(severity, ExcursionSeverity)
        with session_factory() as session:
            query = select(Excursion)
            if status is not None:
                query = query.where(Excursion.status == status)
            if severity is not None:
                query = query.where(Excursion.severity == severity)
            if shipment_id is not None:
                query = query.where(Excursion.shipment_id == shipment_id)
            if sensor_id is not None:
                query = query.where(Excursion.sensor_id == sensor_id)
            query = query.order_by(_sort_column(Excursion, sort, order))
            excursions = list(session.scalars(query).all())
            start = (page - 1) * page_size
            return ExcursionListResponse(
                items=[_excursion_response(item) for item in excursions[start : start + page_size]],
                page=page,
                page_size=page_size,
                total=len(excursions),
            )

    @app.get("/api/excursions/{excursion_id}", response_model=ExcursionDetailResponse)
    def get_excursion(excursion_id: str) -> ExcursionDetailResponse:
        with session_factory() as session:
            excursion = session.get(Excursion, excursion_id)
            if excursion is None:
                raise _not_found("Excursion", excursion_id)
            evidence_links = list(
                session.scalars(
                    select(ExcursionEvidence)
                    .where(ExcursionEvidence.excursion_id == excursion_id)
                    .order_by(ExcursionEvidence.evidence_id)
                    .limit(MAX_EVIDENCE_ITEMS + 1)
                ).all()
            )
            evidence_truncated = len(evidence_links) > MAX_EVIDENCE_ITEMS
            evidence_links = evidence_links[:MAX_EVIDENCE_ITEMS]
            evidence_integrity_warnings = [
                f"Evidence link {link.evidence_id} references missing reading {link.reading_id}"
                for link in evidence_links
                if link.reading is None
            ]
            actions = list(
                session.scalars(
                    select(CorrectiveAction)
                    .where(CorrectiveAction.excursion_id == excursion_id)
                    .order_by(CorrectiveAction.action_id)
                ).all()
            )
            findings = _findings_by_shipment(session, shipment_ids=[excursion.shipment_id]).get(excursion.shipment_id, [])
            sensor = session.get(Sensor, excursion.sensor_id)
            policy = session.get(ThresholdPolicy, excursion.policy_id)
            if sensor is None or policy is None:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": {
                            "code": "INTEGRITY_ERROR",
                            "message": "Excursion references a missing sensor or policy",
                            "details": [excursion_id],
                        }
                    },
                )
            return ExcursionDetailResponse(
                **_excursion_response(excursion).model_dump(),
                policy=_policy_response(policy),
                sensor=_sensor_response(sensor),
                evidence=[
                    EvidenceResponse(
                        **_reading_response(link.reading).model_dump()
                    )
                    for link in evidence_links
                    if link.reading is not None
                ],
                evidence_truncated=evidence_truncated,
                evidence_integrity_warnings=evidence_integrity_warnings,
                data_gap_warnings=[
                    FindingResponse(**finding)
                    for finding in findings
                    if finding["finding_type"] == "telemetry_gap"
                ],
                corrective_actions=[_action_response(action) for action in actions],
                detection_findings=[
                    FindingResponse(**finding)
                    for finding in findings
                    if finding.get("excursion_id") in {None, excursion_id}
                ],
            )

    @app.post(
        "/api/excursions/{excursion_id}/actions",
        response_model=CorrectiveActionResponse,
        status_code=201,
    )
    def add_action(excursion_id: str, request: CorrectiveActionRequest) -> CorrectiveActionResponse:
        with session_factory() as session:
            if session.get(Excursion, excursion_id) is None:
                raise _not_found("Excursion", excursion_id)
            try:
                action = create_corrective_action(
                    session,
                    excursion_id=excursion_id,
                    assigned_to=request.assigned_to,
                    action_type=request.action_type,
                    description=request.description,
                )
                session.commit()
            except IntegrityError as exception:
                session.rollback()
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": {
                            "code": "ACTION_CONFLICT",
                            "message": "Corrective action could not be persisted",
                            "details": [],
                        }
                    },
                ) from exception
            except SQLAlchemyError as exception:
                session.rollback()
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": {
                            "code": "DATABASE_ERROR",
                            "message": "Corrective action could not be persisted",
                            "details": [],
                        }
                    },
                ) from exception
            return _action_response(action)

    _generation_lock = threading.Lock()

    def _get_operational_cache() -> dict[str, Any] | None:
        db_url_str = ""
        try:
            with session_factory() as s:
                db_url_str = str(s.bind.url)
        except Exception:
            pass
        if not db_url_str:
            return None
        cache_path = os.path.join(
            os.path.dirname(__file__), "..", ".cache_operational.pkl"
        )
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    cached = pickle.load(f)
                if cached.get("db_url") == db_url_str:
                    return cached
            except Exception:
                pass
        return None

    def _get_operational_generation() -> dict[str, Any]:
        generation = getattr(app.state, "last_generation", None)
        if generation is not None:
            return generation

        with _generation_lock:
            generation = getattr(app.state, "last_generation", None)
            if generation is not None:
                return generation

            cached = _get_operational_cache()
            if cached is not None:
                app.state.last_generation = cached
                return cached

            with session_factory() as session:
                dataset = load_operational_dataset(session)
                report = validate_dataset(dataset, require_scenario_coverage=False)
                findings = list(detect_dataset(dataset).findings)
                readings_count = len(dataset.readings)
                generation = {
                    "dataset": dataset,
                    "report": report,
                    "findings": findings,
                    "readings_count": readings_count,
                }
                app.state.last_generation = generation
                return generation

    @app.post("/api/validate", response_model=ValidationResponse)
    def validate() -> ValidationResponse:
        cached = _get_operational_cache()
        if cached is not None:
            return _validation_response(cached["report"])
        with session_factory() as session:
            report = validate_dataset(load_operational_dataset(session), require_scenario_coverage=False)
            return _validation_response(report)

    @app.get("/api/quality/summary", response_model=QualitySummaryResponse)
    def quality_summary(
        from_timestamp: datetime | None = Query(default=None, alias="from"),
        to_timestamp: datetime | None = Query(default=None, alias="to"),
    ) -> QualitySummaryResponse:
        _validate_time_window(from_timestamp, to_timestamp)
        generation = _get_operational_generation()
        dataset = generation["dataset"]
        report = generation["report"]
        if "findings" not in generation:
            generation["findings"] = list(detect_dataset(dataset).findings)
        findings = list(generation["findings"])

        findings = [
            finding for finding in findings
            if _finding_in_window(finding, from_timestamp, to_timestamp)
        ]
        shipments = [
            shipment for shipment in dataset.shipments
            if _record_in_window(shipment.planned_departure, from_timestamp, to_timestamp)
        ]
        excursions = [
            excursion for excursion in dataset.excursions
            if _record_in_window(excursion.started_at, from_timestamp, to_timestamp)
        ]
        actions = [
            action for action in dataset.corrective_actions
            if action.status in {CorrectiveActionStatus.OPEN, CorrectiveActionStatus.IN_PROGRESS}
        ]
        evaluation = _evaluation_for_app(app, tuple(findings))

        if from_timestamp is None and to_timestamp is None:
            readings_total = generation.get("readings_count", len(dataset.readings))
        else:
            with session_factory() as session:
                q = select(func.count(SensorReading.reading_id))
                if from_timestamp is not None:
                    q = q.where(SensorReading.recorded_at >= from_timestamp)
                if to_timestamp is not None:
                    q = q.where(SensorReading.recorded_at < to_timestamp)
                readings_total = session.scalar(q) or 0

        return QualitySummaryResponse(
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            shipments_total=len(shipments),
            shipments_by_status=_enum_counts(shipments, "status"),
            excursions_by_status=_enum_counts(excursions, "status"),
            excursions_by_severity=_enum_counts(excursions, "severity"),
            open_corrective_actions=len(actions),
            readings_total=readings_total,
            telemetry_gap_findings=sum(f.finding_type == "telemetry_gap" for f in findings),
            invalid_reading_findings=sum(f.finding_type == "invalid_reading" for f in findings),
            calibration_failure_findings=sum(f.finding_type == "calibration_failure" for f in findings),
            validation_status=_validation_state(report),
            validation_errors=report.errors,
            validation_warnings=report.warnings,
            validation_counts=report.counts,
            evaluation_metrics=evaluation,
        )

    @app.get("/api/exports/{dataset}")
    def export(dataset: str, format: Literal["csv", "json"] = "csv") -> Response:
        model = ALLOWED_EXPORT_DATASETS.get(dataset)
        if model is None or format not in ALLOWED_EXPORT_FORMATS:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_EXPORT",
                        "message": "Dataset or format is not supported",
                        "details": [],
                    }
                },
            )
        with session_factory() as session:
            records = list(session.scalars(select(model).order_by(*model.__table__.primary_key.columns)).all())
            body, media_type = serialize_records(records, format)
        return Response(
            content=body,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{dataset}.{format}"'},
        )

    return app


def _error_response(status_code: int, code: str, message: str, details: list[str]) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def _not_found(entity: str, identifier: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error": {
                "code": "NOT_FOUND",
                "message": f"{entity} not found",
                "details": [identifier],
            }
        },
    )


def _validate_status(value: str | None, enum_type: type[object]) -> None:
    if value is not None and value not in {item.value for item in enum_type}:  # type: ignore[attr-defined]
        raise HTTPException(status_code=400, detail={"error": {
            "code": "INVALID_FILTER", "message": f"Unsupported filter value: {value}", "details": []
        }})


def _validate_time_window(start: datetime | None, end: datetime | None) -> None:
    if start is not None and start.tzinfo is None or end is not None and end.tzinfo is None:
        raise HTTPException(status_code=400, detail={"error": {
            "code": "INVALID_TIME_WINDOW", "message": "Time filters must be timezone-aware", "details": []
        }})
    if start is not None and end is not None and end <= start:
        raise HTTPException(status_code=400, detail={"error": {
            "code": "INVALID_TIME_WINDOW", "message": "The end of the time window must be after its start", "details": []
        }})


def _apply_shipment_filters(query: Any, status: str | None, product_id: str | None, origin: str | None,
                            destination: str | None, start: datetime | None, end: datetime | None) -> Any:
    if status is not None:
        query = query.where(Shipment.status == status)
    if product_id is not None:
        query = query.where(Shipment.product_id == product_id)
    if origin is not None:
        query = query.where(Shipment.origin.ilike(f"%{origin}%"))
    if destination is not None:
        query = query.where(Shipment.destination.ilike(f"%{destination}%"))
    if start is not None:
        query = query.where(Shipment.planned_departure >= start)
    if end is not None:
        query = query.where(Shipment.planned_departure < end)
    return query


def _sort_column(model: type[object], field: str, order: str) -> Any:
    column = getattr(model, field)
    return column.desc() if order == "desc" else column.asc()


def _shipment_response(
    session: Session,
    shipment: Shipment,
    findings: dict[str, list[dict[str, Any]]],
    include_telemetry: bool = True,
) -> ShipmentResponse:
    assignments = list(session.scalars(
        select(ContainerAssignment).where(ContainerAssignment.shipment_id == shipment.shipment_id)
    ).all())
    containers = []
    telemetry: list[ReadingResponse] = []
    telemetry_truncated = False
    for assignment in assignments:
        container = session.get(Container, assignment.container_id)
        if container is None:
            continue
        sensors = list(session.scalars(select(Sensor).where(Sensor.container_id == container.container_id)).all())
        containers.append(ContainerResponse(
            container_id=container.container_id,
            container_type=container.container_type,
            status=container.status.value,
            assignment_id=assignment.assignment_id,
            assigned_from=assignment.assigned_from,
            assigned_to=assignment.assigned_to,
            sensors=[_sensor_response(sensor) for sensor in sensors],
        ))
        if include_telemetry:
            readings = list(session.scalars(
                select(SensorReading)
                .where(
                    SensorReading.assignment_id == assignment.assignment_id,
                    SensorReading.recorded_at >= assignment.assigned_from,
                    SensorReading.recorded_at <= assignment.assigned_to,
                )
                .order_by(SensorReading.recorded_at, SensorReading.reading_id)
                .limit(MAX_TELEMETRY_ITEMS + 1)
            ).all())
            telemetry_truncated = telemetry_truncated or len(readings) > MAX_TELEMETRY_ITEMS
            telemetry.extend(_reading_response(reading) for reading in readings[:MAX_TELEMETRY_ITEMS])
    return ShipmentResponse(
        **_shipment_base(shipment),
        detection_findings=[FindingResponse(**finding) for finding in findings.get(shipment.shipment_id, [])],
        containers=containers,
        route_stops=[
            _route_stop_response(stop)
            for stop in session.scalars(
                select(RouteStop).where(RouteStop.shipment_id == shipment.shipment_id).order_by(RouteStop.sequence_number)
            ).all()
        ],
        custody_events=[
            _custody_response(event)
            for event in session.scalars(
                select(CustodyEvent).where(CustodyEvent.shipment_id == shipment.shipment_id).order_by(CustodyEvent.event_time)
            ).all()
        ],
        excursions=[
            _excursion_response(excursion)
            for excursion in session.scalars(
                select(Excursion).where(Excursion.shipment_id == shipment.shipment_id).order_by(Excursion.started_at)
            ).all()
        ],
        telemetry=telemetry[:MAX_TELEMETRY_ITEMS],
        telemetry_truncated=telemetry_truncated or len(telemetry) > MAX_TELEMETRY_ITEMS,
    )


def _shipment_base(shipment: Shipment) -> dict[str, Any]:
    return {
        "shipment_id": shipment.shipment_id,
        "product_id": shipment.product_id,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "planned_departure": shipment.planned_departure,
        "planned_delivery": shipment.planned_delivery,
        "actual_departure": shipment.actual_departure,
        "actual_delivery": shipment.actual_delivery,
        "issue_type": shipment.issue_type,
        "status": shipment.status.value,
    }


def _sensor_response(sensor: Sensor) -> SensorResponse:
    return SensorResponse(
        sensor_id=sensor.sensor_id,
        sensor_type=sensor.sensor_type.value,
        calibrated_at=sensor.calibrated_at,
        calibration_due_at=sensor.calibration_due_at,
        status=sensor.status.value,
    )


def _reading_response(reading: SensorReading) -> ReadingResponse:
    return ReadingResponse(
        reading_id=reading.reading_id,
        sensor_id=reading.sensor_id,
        recorded_at=reading.recorded_at,
        value=reading.value,
        unit=reading.unit,
        quality_status=reading.quality_status.value,
        issue_type=reading.issue_type,
    )


def _route_stop_response(stop: RouteStop) -> RouteStopResponse:
    return RouteStopResponse(
        route_stop_id=stop.route_stop_id,
        sequence_number=stop.sequence_number,
        location=stop.location,
        planned_arrival=stop.planned_arrival,
        actual_arrival=stop.actual_arrival,
        actual_departure=stop.actual_departure,
        status=stop.status.value,
    )


def _custody_response(event: CustodyEvent) -> CustodyEventResponse:
    return CustodyEventResponse(
        custody_event_id=event.custody_event_id,
        event_time=event.event_time,
        event_type=event.event_type.value,
        from_party=event.from_party,
        to_party=event.to_party,
        location=event.location,
        evidence_ref=event.evidence_ref,
    )


def _excursion_response(excursion: Excursion) -> ExcursionResponse:
    return ExcursionResponse(
        excursion_id=excursion.excursion_id,
        assignment_id=excursion.assignment_id,
        container_id=excursion.container_id,
        shipment_id=excursion.shipment_id,
        sensor_id=excursion.sensor_id,
        policy_id=excursion.policy_id,
        started_at=excursion.started_at,
        ended_at=excursion.ended_at,
        duration_minutes=excursion.duration_minutes,
        severity=excursion.severity.value,
        status=excursion.status.value,
        decision_reason=excursion.decision_reason,
    )


def _policy_response(policy: ThresholdPolicy) -> PolicyResponse:
    return PolicyResponse(
        policy_id=policy.policy_id,
        product_id=policy.product_id,
        version=policy.version,
        min_temp_c=policy.min_temp_c,
        max_temp_c=policy.max_temp_c,
        max_excursion_minutes=policy.max_excursion_minutes,
        min_humidity_pct=policy.min_humidity_pct,
        max_humidity_pct=policy.max_humidity_pct,
        effective_from=policy.effective_from,
        effective_to=policy.effective_to,
    )


def _action_response(action: CorrectiveAction) -> CorrectiveActionResponse:
    return CorrectiveActionResponse(
        action_id=action.action_id,
        excursion_id=action.excursion_id,
        assigned_to=action.assigned_to,
        action_type=action.action_type.value,
        description=action.description,
        created_at=action.created_at,
        completed_at=action.completed_at,
        status=action.status.value,
        outcome=action.outcome,
    )


def _finding_response(finding: DetectionFinding) -> dict[str, Any]:
    return {
        "finding_id": finding.finding_id,
        "finding_type": finding.finding_type,
        "reason": finding.reason,
        "shipment_id": finding.shipment_id,
        "sensor_id": finding.sensor_id,
        "assignment_id": finding.assignment_id,
        "policy_id": finding.policy_id,
        "reading_ids": list(finding.reading_ids),
        "excursion_id": finding.excursion_id,
        "started_at": finding.started_at,
        "ended_at": finding.ended_at,
        "duration_minutes": finding.duration_minutes,
        "severity": finding.severity,
        "status": finding.status,
    }


def _findings_by_shipment(
    session: Session, shipment_ids: Iterable[str] | None = None
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for finding in detect_persisted_dataset(session, shipment_ids=shipment_ids).findings:
        grouped.setdefault(finding.shipment_id, []).append(_finding_response(finding))
    return grouped


def _enum_counts(records: list[object], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = getattr(record, attribute)
        key = value.value if hasattr(value, "value") else str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _quality_state(findings: list[dict[str, Any]]) -> Literal["passed", "warnings", "failed"]:
    if any(item["finding_type"] in {"invalid_attribution", "policy_selection_error"} for item in findings):
        return "failed"
    if findings:
        return "warnings"
    return "passed"


def _validation_response(report: ValidationReport) -> ValidationResponse:
    return ValidationResponse(
        validation_status="passed" if report.passed else "failed",
        errors=report.errors,
        warnings=report.warnings,
        counts=report.counts,
        checks=_validation_checks(report),
    )


def _validation_checks(report: ValidationReport) -> list[ValidationCheckResponse]:
    return [
        ValidationCheckResponse(
            name="operational_record_validation",
            status="failed" if report.errors else "warning" if report.warnings else "passed",
            count=len(report.errors) + len(report.warnings),
            examples=(report.errors + report.warnings)[:3],
        ),
        ValidationCheckResponse(
            name="record_counts",
            status="passed",
            count=sum(report.counts.values()),
            examples=[],
        ),
    ]


def _evaluation_for_app(
    app: FastAPI, findings: tuple[DetectionFinding, ...]
) -> dict[str, Any]:
    generation = getattr(app.state, "last_generation", None)
    if generation is None:
        return {
            "available": False,
            "unavailable_reason": (
                "Ground truth is not persisted in the operational database and is "
                "unavailable after an API restart or externally loaded dataset"
            ),
            "evaluation_unit": "scenario case",
            "matching_rule": "shipment_id plus documented finding-type mapping",
            "confusion_matrix": None,
            "metrics": {},
        }
    return evaluate_ground_truth(generation["dataset"].ground_truth, findings).as_dict()


def _validation_state(report: ValidationReport) -> Literal["passed", "warnings", "failed"]:
    if report.errors:
        return "failed"
    if report.warnings:
        return "warnings"
    return "passed"


def _record_in_window(value: datetime, start: datetime | None, end: datetime | None) -> bool:
    return (start is None or value >= start) and (end is None or value < end)


def _finding_in_window(
    finding: DetectionFinding, start: datetime | None, end: datetime | None
) -> bool:
    value = finding.started_at or finding.ended_at
    return value is None or _record_in_window(value, start, end)
