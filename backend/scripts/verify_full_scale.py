from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import create_engine_for_url, create_schema, persist_dataset
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
from backend.app.services.detection import detect_dataset
from backend.app.services.evaluation import evaluate_ground_truth
from backend.app.services.export import export_dataset
from backend.app.services.generator import (
    GeneratorConfig,
    ProductSpec,
    SCENARIO_TYPES,
    generate_dataset,
)
from backend.app.services.validation import validate_dataset


EXPECTED_ARTIFACTS = frozenset(
    {
        f"{name}.{extension}"
        for name in (
            "products",
            "threshold_policies",
            "shipments",
            "containers",
            "container_assignments",
            "sensors",
            "sensor_readings",
            "route_stops",
            "excursions",
            "excursion_evidence",
            "custody_events",
            "corrective_actions",
            "ground_truth",
        )
        for extension in ("csv", "json")
    }
    | {"generation_config.json", "source_manifest.json", "validation_summary.json"}
)

MODEL_COUNTS = {
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


def build_baseline_config() -> GeneratorConfig:
    scenario_counts = {
        scenario: (900 if scenario == "normal" else 10)
        for scenario in SCENARIO_TYPES
    }
    return GeneratorConfig(
        seed=20261022,
        shipment_count=1000,
        container_count=300,
        scenario_counts=scenario_counts,
        products=(
            ProductSpec(
                "Baseline product",
                "cold_chain",
                min_temp_c=2,
                max_temp_c=8,
                max_excursion_minutes=30,
                min_humidity_pct=30,
                max_humidity_pct=70,
            ),
        ),
        sampling_interval_minutes=5,
        min_trip_days=2,
        max_trip_days=5,
    )


def verify_artifacts(
    output_dir: str | Path, expected_counts: dict[str, int]
) -> dict[str, Any]:
    destination = Path(output_dir)
    actual = {path.name for path in destination.iterdir() if path.is_file()}
    missing = sorted(EXPECTED_ARTIFACTS - actual)
    unexpected = sorted(actual - EXPECTED_ARTIFACTS - {"verification_report.json"})
    files: dict[str, dict[str, int]] = {}
    row_errors: list[str] = []

    for name in sorted(EXPECTED_ARTIFACTS):
        path = destination / name
        if not path.exists():
            continue
        size = path.stat().st_size
        row_count = -1
        if path.suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as handle:
                row_count = max(sum(1 for _ in csv.reader(handle)) - 1, 0)
        elif path.suffix == ".json":
            value = json.loads(path.read_text(encoding="utf-8"))
            row_count = len(value) if isinstance(value, list) else 1
        files[name] = {"size_bytes": size, "row_count": row_count}
        expected_name = _count_name(name)
        if expected_name in expected_counts and row_count != expected_counts[expected_name]:
            row_errors.append(
                f"{name}: expected {expected_counts[expected_name]} rows, got {row_count}"
            )

    return {
        "passed": not missing and not row_errors,
        "missing": missing,
        "unexpected": unexpected,
        "row_errors": row_errors,
        "files": files,
    }


def _count_name(filename: str) -> str:
    return {
        "container_assignments": "assignments",
        "sensor_readings": "readings",
    }.get(filename.rsplit(".", 1)[0], filename.rsplit(".", 1)[0])


def _phase(
    logger: logging.Logger,
    phase_name: str,
    operation: Any,
    timeout_seconds: float,
) -> tuple[Any, float]:
    started = time.perf_counter()
    logger.info("phase_started phase=%s", phase_name)
    result = operation()
    elapsed = time.perf_counter() - started
    logger.info("phase_completed phase=%s elapsed_seconds=%.3f", phase_name, elapsed)
    if elapsed > timeout_seconds:
        raise TimeoutError(
            f"phase {phase_name} exceeded {timeout_seconds:.3f} seconds "
            f"(actual {elapsed:.3f})"
        )
    return result, elapsed


def _readback_counts(session_factory: sessionmaker) -> dict[str, int]:
    session = session_factory()
    try:
        return {
            name: session.scalar(select(func.count()).select_from(model)) or 0
            for name, model in MODEL_COUNTS.items()
        }
    finally:
        session.close()


def _configure_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("yottaflex.full_scale_verification")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(logging.StreamHandler(sys.stdout))
    return logger


def run_verification(
    database_path: str | Path,
    output_dir: str | Path,
    log_path: str | Path,
    phase_timeout_seconds: float = 600.0,
    config: GeneratorConfig | None = None,
) -> dict[str, Any]:
    database = Path(database_path).resolve()
    output = Path(output_dir).resolve()
    log_file = Path(log_path).resolve()
    if database.exists():
        raise FileExistsError(f"database path already exists: {database}")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    logger = _configure_logging(log_file)
    effective_config = config or build_baseline_config()
    database_url = f"sqlite:///{database}"
    timings: dict[str, float] = {}
    report: dict[str, Any] = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_path": str(database),
        "output_dir": str(output),
        "log_path": str(log_file),
    }
    schema_engine = None
    persistence_engine = None
    try:
        dataset, timings["generation"] = _phase(
            logger, "generation", lambda: generate_dataset(effective_config), phase_timeout_seconds
        )
        validation, timings["validation"] = _phase(
            logger, "validation", lambda: validate_dataset(dataset), phase_timeout_seconds
        )
        report["generated_counts"] = validation.counts
        report["validation"] = {
            "passed": validation.passed,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }
        if not validation.passed:
            raise RuntimeError(f"validation failed: {validation.errors[:10]}")

        findings_report, timings["detection"] = _phase(
            logger, "detection", lambda: detect_dataset(dataset), phase_timeout_seconds
        )
        evaluation_result, timings["evaluation"] = _phase(
            logger,
            "evaluation",
            lambda: evaluate_ground_truth(dataset.ground_truth, findings_report.findings),
            phase_timeout_seconds,
        )
        report["evaluation"] = evaluation_result.as_dict()

        schema_engine = create_schema(database_url)
        persistence_engine = create_engine_for_url(database_url)
        session_factory = sessionmaker(
            bind=persistence_engine, expire_on_commit=False
        )
        _, timings["persistence"] = _phase(
            logger,
            "persistence",
            lambda: persist_dataset(dataset, session_factory),
            phase_timeout_seconds,
        )
        readback, timings["read_back"] = _phase(
            logger,
            "read_back",
            lambda: _readback_counts(session_factory),
            phase_timeout_seconds,
        )
        report["readback_counts"] = readback
        if readback != {
            name: len(records)
            for name, records in zip(
                MODEL_COUNTS,
                dataset.operational_collections(),
                strict=True,
            )
        }:
            raise RuntimeError("database read-back counts do not match generated counts")

        _, timings["export"] = _phase(
            logger,
            "export",
            lambda: export_dataset(dataset, validation, output),
            phase_timeout_seconds,
        )
        artifacts, timings["artifact_verification"] = _phase(
            logger,
            "artifact_verification",
            lambda: verify_artifacts(output, validation.counts | {"ground_truth": len(dataset.ground_truth)}),
            phase_timeout_seconds,
        )
        report["artifacts"] = artifacts
        if not artifacts["passed"]:
            raise RuntimeError(f"artifact verification failed: {artifacts}")
        report["timings_seconds"] = timings
        report["status"] = "completed"
        logger.info("verification_completed status=completed")
        (output / "verification_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return report
    except Exception as exc:
        report["timings_seconds"] = timings
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        logger.exception("verification_failed")
        (output / "verification_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        raise
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        if persistence_engine is not None:
            persistence_engine.dispose()
        for handler in list(logger.handlers):
            try:
                handler.close()
            except Exception:
                pass
            logger.removeHandler(handler)



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-path", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--log-path", required=True, type=Path)
    parser.add_argument("--phase-timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run verification on a fast smoke-test dataset (11 shipments)",
    )
    args = parser.parse_args()
    smoke_config = (
        GeneratorConfig(
            seed=20261022,
            shipment_count=len(SCENARIO_TYPES),
            container_count=len(SCENARIO_TYPES),
            scenario_counts={scenario: 1 for scenario in SCENARIO_TYPES},
            products=(
                ProductSpec(
                    "Smoke product",
                    "cold_chain",
                    min_temp_c=2,
                    max_temp_c=8,
                    max_excursion_minutes=30,
                    min_humidity_pct=30,
                    max_humidity_pct=70,
                ),
            ),
            sampling_interval_minutes=5,
            min_trip_days=2,
            max_trip_days=2,
        )
        if args.smoke
        else None
    )
    try:
        run_verification(
            args.database_path,
            args.output_dir,
            args.log_path,
            args.phase_timeout_seconds,
            config=smoke_config,
        )
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
