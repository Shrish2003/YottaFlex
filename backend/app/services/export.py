from __future__ import annotations

import csv
from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from collections.abc import Iterable
from typing import Any

from backend.app.core.time import now_utc
from backend.app.models.base import SCHEMA_VERSION
from backend.app.services.generator import GeneratedDataset
from backend.app.services.validation import ValidationReport


def export_dataset(
    dataset: GeneratedDataset,
    report: ValidationReport,
    output_dir: str | Path,
) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    operational = {
        "products": dataset.products,
        "threshold_policies": dataset.policies,
        "shipments": dataset.shipments,
        "containers": dataset.containers,
        "container_assignments": dataset.assignments,
        "sensors": dataset.sensors,
        "sensor_readings": dataset.readings,
        "route_stops": dataset.route_stops,
        "excursions": dataset.excursions,
        "excursion_evidence": dataset.excursion_evidence,
        "custody_events": dataset.custody_events,
        "corrective_actions": dataset.corrective_actions,
    }
    for name, records in operational.items():
        _write_records(destination / f"{name}.json", records)
        _write_records(destination / f"{name}.csv", records)
    _write_records(destination / "ground_truth.json", dataset.ground_truth)
    _write_records(destination / "ground_truth.csv", dataset.ground_truth)
    _write_json(destination / "generation_config.json", _object_row(dataset.config))
    _write_json(
        destination / "source_manifest.json",
        {
            "data_origin": "synthetic",
            "generator_version": dataset.config.generator_version if dataset.config else None,
            "schema_version": SCHEMA_VERSION,
            "seed": dataset.config.seed if dataset.config else None,
            "generated_at_utc": now_utc().isoformat().replace("+00:00", "Z"),
            "record_counts": report.counts,
        },
    )
    _write_json(
        destination / "validation_summary.json",
        {"passed": report.passed, "errors": report.errors, "warnings": report.warnings, "counts": report.counts},
    )
    return destination


def serialize_records(records: Iterable[Any], file_format: str) -> tuple[bytes, str]:
    """Serialize an explicit operational record collection for an API download."""

    rows = [_object_row(record) for record in records]
    if file_format == "json":
        return (
            (json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
                "utf-8"
            ),
            "application/json",
        )
    if file_format != "csv":
        raise ValueError(f"unsupported export format: {file_format}")
    import io

    output = io.StringIO(newline="")
    keys = sorted(rows[0]) if rows else []
    writer = csv.DictWriter(output, fieldnames=keys)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8"), "text/csv; charset=utf-8"


def _object_row(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        raw = asdict(value)
    elif hasattr(value, "__table__"):
        raw = {}
        for column in value.__table__.columns:
            item = getattr(value, column.name)
            if item is None and column.name.endswith("_id"):
                relationship = getattr(value, column.name[:-3], None)
                if relationship is not None:
                    item = getattr(relationship, column.name)
            raw[column.name] = item
    else:
        raw = dict(value)
    return {key: _serialize(item) for key, item in raw.items()}


def _serialize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat().replace("+00:00", "Z")
    return str(value) if value.__class__.__name__ == "Decimal" else value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_records(path: Path, records: Iterable[Any]) -> None:
    iterator = iter(records)
    first = next(iterator, None)
    if path.suffix == ".json":
        with path.open("w", encoding="utf-8") as handle:
            handle.write("[")
            if first is not None:
                handle.write("\n  " + json.dumps(_object_row(first), sort_keys=True))
                for record in iterator:
                    handle.write(",\n  " + json.dumps(_object_row(record), sort_keys=True))
                handle.write("\n")
            handle.write("]\n")
        return
    first_row = _object_row(first) if first is not None else {}
    keys = sorted(first_row)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        if first is not None:
            writer.writerow(first_row)
            for record in iterator:
                writer.writerow(_object_row(record))
