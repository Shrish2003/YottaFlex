from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.database import (
    create_schema,
    persist_dataset,
    persist_dataset_orm,
)
from backend.app.services.generator import (
    GeneratorConfig,
    ProductSpec,
    SCENARIO_TYPES,
    generate_dataset,
)
from backend.app.services.validation import validate_dataset


def build_config(shipment_count: int) -> GeneratorConfig:
    scenario_counts = {scenario: 0 for scenario in SCENARIO_TYPES}
    scenario_counts["normal"] = shipment_count
    return GeneratorConfig(
        seed=20261022,
        shipment_count=shipment_count,
        container_count=max(1, min(shipment_count, 30)),
        scenario_counts=scenario_counts,
        products=(
            ProductSpec(
                "Benchmark product",
                "cold_chain",
                2,
                8,
                30,
                30,
                70,
            ),
        ),
    )


def timed_persist(dataset, persist_function, path: Path) -> float:
    database_url = "sqlite:///" + str(path)
    create_schema(database_url).dispose()
    engine = create_engine(database_url, future=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    started = time.perf_counter()
    persist_function(dataset, factory)
    elapsed = time.perf_counter() - started
    engine.dispose()
    return elapsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shipments", type=int, default=25)
    args = parser.parse_args()
    config = build_config(args.shipments)
    dataset = generate_dataset(config)
    report = validate_dataset(dataset, require_scenario_coverage=False)
    if not report.passed:
        raise RuntimeError(report.errors)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        orm_elapsed = timed_persist(
            generate_dataset(config), persist_dataset_orm, root / "orm.sqlite"
        )
        bulk_elapsed = timed_persist(
            generate_dataset(config), persist_dataset, root / "bulk.sqlite"
        )
    records = sum(report.counts.values())
    print(f"shipments={args.shipments}")
    print(f"records={records}")
    print(f"orm_seconds={orm_elapsed:.3f}")
    print(f"orm_records_per_second={records / orm_elapsed:.3f}")
    print(f"bulk_seconds={bulk_elapsed:.3f}")
    print(f"bulk_records_per_second={records / bulk_elapsed:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
