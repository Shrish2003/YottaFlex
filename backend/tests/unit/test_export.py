import tempfile
import unittest
import json
from pathlib import Path

from backend.app.services.export import export_dataset
from backend.app.services.generator import SCENARIO_TYPES, generate_dataset
from backend.app.services.generator import GeneratorConfig, ProductSpec
from backend.tests.unit.test_generator import config
from backend.app.services.validation import validate_dataset
from backend.app.models.base import SCHEMA_VERSION
from decimal import Decimal


class ExportTests(unittest.TestCase):
    def test_exports_operational_and_separate_ground_truth_artifacts(self) -> None:
        dataset = generate_dataset(config())
        report = validate_dataset(dataset)
        with tempfile.TemporaryDirectory() as directory:
            output = export_dataset(dataset, report, Path(directory))
            self.assertTrue((output / "sensor_readings.csv").exists())
            self.assertTrue((output / "ground_truth.json").exists())
            operational_text = (output / "sensor_readings.json").read_text(encoding="utf-8")
            self.assertNotIn("expected_detector_decision", operational_text)
            self.assertEqual(len((output / "ground_truth.csv").read_text(encoding="utf-8").splitlines()) - 1, len(SCENARIO_TYPES))

    def test_same_seed_reproducible_exports_excluding_volatile_manifest_metadata(self) -> None:
        first_dataset = generate_dataset(config())
        second_dataset = generate_dataset(config())
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = export_dataset(first_dataset, validate_dataset(first_dataset), Path(first_dir))
            second = export_dataset(second_dataset, validate_dataset(second_dataset), Path(second_dir))
            reproducible_files = [
                "products.json",
                "threshold_policies.json",
                "shipments.json",
                "containers.json",
                "sensors.json",
                "sensor_readings.json",
                "route_stops.json",
                "excursions.json",
                "custody_events.json",
                "corrective_actions.json",
                "ground_truth.json",
                "generation_config.json",
                "validation_summary.json",
            ]
            for filename in reproducible_files:
                self.assertEqual(
                    json.loads((first / filename).read_text(encoding="utf-8")),
                    json.loads((second / filename).read_text(encoding="utf-8")),
                    filename,
                )

    def test_wrong_product_fixture_exports_operational_policy_separately(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"wrong_product_threshold": 1},
                products=(
                    ProductSpec(
                        "Smoke",
                        "cold_chain",
                        Decimal("2"),
                        Decimal("8"),
                        30,
                    ),
                ),
            )
        )
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertTrue(report.passed, report.errors)
        with tempfile.TemporaryDirectory() as directory:
            output = export_dataset(dataset, report, Path(directory))
            products = json.loads((output / "products.json").read_text(encoding="utf-8"))
            policies = json.loads(
                (output / "threshold_policies.json").read_text(encoding="utf-8")
            )
            excursions = json.loads((output / "excursions.json").read_text(encoding="utf-8"))
            ground_truth = json.loads(
                (output / "ground_truth.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(products), 2)
            self.assertEqual(len(policies), 2)
            self.assertNotEqual(excursions[0]["policy_id"], ground_truth[0]["expected_policy_id"])
            self.assertNotIn("expected_detector_decision", excursions[0])
            self.assertIn("expected_detector_decision", ground_truth[0])

    def test_evidence_and_manifest_schema_are_exported(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"brief_excursion": 1},
                products=config().products,
            )
        )
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertTrue(report.passed, report.errors)
        with tempfile.TemporaryDirectory() as directory:
            output = export_dataset(dataset, report, Path(directory))
            evidence = json.loads(
                (output / "excursion_evidence.json").read_text(encoding="utf-8")
            )
            manifest = json.loads(
                (output / "source_manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(evidence)
            self.assertEqual(manifest["schema_version"], SCHEMA_VERSION)
            self.assertEqual(manifest["record_counts"]["excursion_evidence"], len(evidence))
            self.assertNotIn("expected_detector_decision", evidence[0])

    def test_export_reports_invalid_output_path(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"normal": 1},
                products=config().products,
            )
        )
        report = validate_dataset(dataset, require_scenario_coverage=False)
        with tempfile.TemporaryDirectory() as directory:
            output_file = Path(directory) / "not-a-directory"
            output_file.write_text("occupied", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_dataset(dataset, report, output_file)


if __name__ == "__main__":
    unittest.main()
