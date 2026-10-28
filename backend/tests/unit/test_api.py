import tempfile
import unittest
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from backend.app.api import create_app
from backend.app.db.database import create_schema, persist_dataset
from backend.app.services.generator import (
    GeneratorConfig,
    ProductSpec,
    generate_dataset,
)
from backend.app.models.entities import ExcursionEvidence, CorrectiveAction, SensorReading


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_url = "sqlite:///" + str(Path(self.temp_dir.name) / "api.sqlite")
        self.engine = create_schema(database_url)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"brief_excursion": 1},
                products=(
                    ProductSpec(
                        "API fixture",
                        "cold_chain",
                        Decimal("2"),
                        Decimal("8"),
                        30,
                    ),
                ),
            )
        )
        persist_dataset(self.dataset, self.session_factory)
        self.client = TestClient(create_app(self.session_factory))

    def tearDown(self) -> None:
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_shipment_and_excursion_endpoints_use_persisted_data(self) -> None:
        shipment_id = self.dataset.shipments[0].shipment_id
        excursion_id = self.dataset.excursions[0].excursion_id

        shipments = self.client.get("/api/shipments")
        self.assertEqual(shipments.status_code, 200)
        self.assertEqual(shipments.json()["total"], 1)
        self.assertTrue(shipments.json()["items"][0]["detection_findings"])

        shipment = self.client.get(f"/api/shipments/{shipment_id}")
        self.assertEqual(shipment.status_code, 200)
        self.assertEqual(shipment.json()["shipment_id"], shipment_id)
        self.assertNotIn("ground_truth", shipment.json())

        excursions = self.client.get("/api/excursions?status=open")
        self.assertEqual(excursions.status_code, 200)
        self.assertEqual(excursions.json()["total"], 1)

        detail = self.client.get(f"/api/excursions/{excursion_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["excursion_id"], excursion_id)
        self.assertTrue(detail.json()["evidence"])
        self.assertTrue(detail.json()["detection_findings"])

    def test_missing_resources_return_contract_error(self) -> None:
        shipment = self.client.get("/api/shipments/missing")
        self.assertEqual(shipment.status_code, 404)
        self.assertEqual(shipment.json()["error"]["code"], "NOT_FOUND")

        excursion = self.client.get("/api/excursions/missing")
        self.assertEqual(excursion.status_code, 404)
        self.assertEqual(excursion.json()["error"]["code"], "NOT_FOUND")

    def test_pagination_validation_returns_422(self) -> None:
        response = self.client.get("/api/shipments?page=0")
        self.assertEqual(response.status_code, 422)

    def test_complete_api_workflow_and_bounded_operational_exports(self) -> None:
        empty_dir = tempfile.TemporaryDirectory()
        empty_engine = create_schema("sqlite:///" + str(Path(empty_dir.name) / "empty.sqlite"))
        empty_factory = sessionmaker(bind=empty_engine, expire_on_commit=False)
        empty_client = TestClient(create_app(empty_factory))
        empty_quality = empty_client.get("/api/quality/summary")
        self.assertEqual(empty_quality.status_code, 200)
        self.assertEqual(empty_quality.json()["shipments_total"], 0)
        empty_engine.dispose()
        empty_dir.cleanup()

        dataset_request = {
            "seed": 20261022,
            "shipment_count": 1,
            "container_count": 1,
            "sampling_interval_minutes": 5,
            "min_trip_days": 2,
            "max_trip_days": 2,
            "scenario_counts": {"brief_excursion": 1},
            "products": [
                {
                    "name": "API generated product",
                    "category": "cold_chain",
                    "min_temp_c": "2",
                    "max_temp_c": "8",
                    "max_excursion_minutes": 30,
                }
            ],
        }
        generated = self.client.post("/api/generate", json=dataset_request)
        self.assertEqual(generated.status_code, 409)

        fresh_dir = tempfile.TemporaryDirectory()
        fresh_engine = create_schema("sqlite:///" + str(Path(fresh_dir.name) / "generated.sqlite"))
        fresh_factory = sessionmaker(bind=fresh_engine, expire_on_commit=False)
        fresh_client = TestClient(create_app(fresh_factory))
        generated = fresh_client.post("/api/generate", json=dataset_request)
        self.assertEqual(generated.status_code, 201, generated.text)
        self.assertEqual(generated.json()["counts"]["shipments"], 1)

        shipment_id = "SHP-2026-000001"
        shipment = fresh_client.get(
            "/api/shipments",
            params={
                "status": "delivered",
                "product_id": "PRD-000001",
                "origin": "Origin-001",
                "sort": "planned_departure",
            },
        )
        self.assertEqual(shipment.status_code, 200)
        self.assertEqual(shipment.json()["total"], 1)
        self.assertTrue(shipment.json()["items"][0]["telemetry"])

        detail = fresh_client.get(f"/api/shipments/{shipment_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("route_stops", detail.json())
        summary = fresh_client.get(f"/api/shipments/{shipment_id}/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["shipment_id"], shipment_id)

        excursions = fresh_client.get("/api/excursions?status=open")
        self.assertEqual(excursions.status_code, 200)
        excursion_id = excursions.json()["items"][0]["excursion_id"]
        excursion = fresh_client.get(f"/api/excursions/{excursion_id}")
        self.assertEqual(excursion.status_code, 200)
        self.assertTrue(excursion.json()["evidence"][0]["value"])
        self.assertIn("min_temp_c", excursion.json()["policy"])
        action = fresh_client.post(
            f"/api/excursions/{excursion_id}/actions",
            json={
                "assigned_to": "quality_engineer",
                "action_type": "review",
                "description": "Review persisted excursion evidence",
            },
        )
        self.assertEqual(action.status_code, 201, action.text)
        self.assertEqual(action.json()["status"], "open")

        validation = fresh_client.post("/api/validate")
        self.assertEqual(validation.status_code, 200)
        self.assertTrue(validation.json()["checks"])
        quality = fresh_client.get("/api/quality/summary")
        self.assertEqual(quality.status_code, 200)
        self.assertEqual(quality.json()["shipments_total"], 1)
        self.assertTrue(quality.json()["evaluation_metrics"]["available"])

        export = fresh_client.get("/api/exports/shipments?format=json")
        self.assertEqual(export.status_code, 200)
        self.assertIn(shipment_id, export.text)
        ground_truth = fresh_client.get("/api/exports/ground_truth?format=json")
        self.assertEqual(ground_truth.status_code, 400)
        unsupported = fresh_client.get("/api/exports/shipments?format=xml")
        self.assertEqual(unsupported.status_code, 422)
        naive_generation = fresh_client.post(
            "/api/generate",
            json={**dataset_request, "start_datetime": "2026-01-01T00:00:00"},
        )
        self.assertEqual(naive_generation.status_code, 422)
        fresh_engine.dispose()
        fresh_dir.cleanup()

    def test_validation_reports_warning_and_failure_checks(self) -> None:
        warning = self.client.post("/api/validate")
        self.assertEqual(warning.status_code, 200)
        self.assertIn(warning.json()["validation_status"], {"passed", "warning"})
        with self.session_factory() as session:
            shipment = session.get(type(self.dataset.shipments[0]), self.dataset.shipments[0].shipment_id)
            shipment.issue_type = "delivery_before_departure"
            shipment.actual_delivery = shipment.actual_departure - timedelta(minutes=1)
            session.commit()
        failed = self.client.post("/api/validate")
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(failed.json()["validation_status"], "passed")
        with self.session_factory() as session:
            reading = session.scalar(select(SensorReading))
            reading.unit = "invalid"
            session.commit()
        failed = self.client.post("/api/validate")
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(failed.json()["validation_status"], "failed")
        self.assertTrue(any(check["status"] == "failed" for check in failed.json()["checks"]))

    def test_telemetry_truncation_and_missing_evidence_are_explicit(self) -> None:
        with self.session_factory() as session:
            readings = list(session.scalars(select(SensorReading).limit(501)).all())
            self.assertEqual(len(readings), 501)
            link = session.scalar(select(ExcursionEvidence))
            missing_id = link.reading_id
            session.commit()
            session.connection().exec_driver_sql("PRAGMA foreign_keys=OFF")
            session.delete(session.get(SensorReading, missing_id))
            session.commit()
        shipment = self.client.get(f"/api/shipments/{self.dataset.shipments[0].shipment_id}")
        self.assertEqual(shipment.status_code, 200)
        self.assertTrue(shipment.json()["telemetry_truncated"])
        detail = self.client.get(f"/api/excursions/{self.dataset.excursions[0].excursion_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["evidence_integrity_warnings"])

    def test_generation_failure_rolls_back_database(self) -> None:
        class FailingSession(Session):
            def commit(self) -> None:
                raise SQLAlchemyError("controlled commit failure")

        failing_engine = create_schema(
            "sqlite:///" + str(Path(self.temp_dir.name) / "generation_failure.sqlite")
        )
        failing_factory = lambda: FailingSession(bind=failing_engine, expire_on_commit=False)
        failing_client = TestClient(create_app(failing_factory))
        with failing_engine.connect() as connection:
            before = connection.exec_driver_sql("select count(*) from shipments").scalar_one()
        response = failing_client.post("/api/generate", json={
            "start_datetime": "2027-01-01T00:00:00Z",
            "shipment_count": 1,
            "container_count": 1,
            "scenario_counts": {"normal": 1},
            "products": [{
                "name": "Failure product",
                "category": "cold_chain",
                "min_temp_c": 2,
                "max_temp_c": 8,
                "max_excursion_minutes": 30,
            }],
        })
        self.assertEqual(response.status_code, 500)
        with failing_engine.connect() as connection:
            after = connection.exec_driver_sql("select count(*) from shipments").scalar_one()
        self.assertEqual(after, before)
        failing_engine.dispose()

    def test_action_commit_failure_rolls_back_database(self) -> None:
        excursion_id = self.dataset.excursions[0].excursion_id
        class FailingSession(Session):
            def commit(self) -> None:
                raise SQLAlchemyError("controlled commit failure")

        failing_factory = lambda: FailingSession(bind=self.engine, expire_on_commit=False)
        failing_client = TestClient(create_app(failing_factory))
        response = failing_client.post(
            f"/api/excursions/{excursion_id}/actions",
            json={
                "assigned_to": "quality_engineer",
                "action_type": "review",
                "description": "Failure test",
            },
        )
        self.assertEqual(response.status_code, 500)
        with self.session_factory() as session:
            actions = session.scalars(
                select(CorrectiveAction).where(CorrectiveAction.description == "Failure test")
            ).all()
            self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()
