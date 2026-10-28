import json
import tempfile
import unittest
from pathlib import Path

from backend.scripts.verify_full_scale import EXPECTED_ARTIFACTS, verify_artifacts


class FullScaleVerificationTests(unittest.TestCase):
    def test_artifact_verification_reports_missing_and_row_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "products.csv").write_text(
                "product_id\nPRD-000001\n", encoding="utf-8"
            )
            (output / "products.json").write_text(
                json.dumps([{"product_id": "PRD-000001"}]), encoding="utf-8"
            )
            result = verify_artifacts(output, {"products": 2})
            self.assertFalse(result["passed"])
            self.assertIn("containers.csv", result["missing"])
            self.assertTrue(result["row_errors"])

    def test_expected_artifact_set_includes_ground_truth_and_metadata(self) -> None:
        self.assertIn("ground_truth.csv", EXPECTED_ARTIFACTS)
        self.assertIn("ground_truth.json", EXPECTED_ARTIFACTS)
        self.assertIn("generation_config.json", EXPECTED_ARTIFACTS)
        self.assertIn("source_manifest.json", EXPECTED_ARTIFACTS)
        self.assertIn("validation_summary.json", EXPECTED_ARTIFACTS)
        self.assertIn("excursion_evidence.json", EXPECTED_ARTIFACTS)

    def test_smoke_run_verification_pipeline(self) -> None:
        from decimal import Decimal
        from backend.app.services.generator import GeneratorConfig, ProductSpec, SCENARIO_TYPES
        from backend.scripts.verify_full_scale import run_verification

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "test.sqlite"
            out_dir = temp_path / "artifacts"
            log_path = temp_path / "test.log"
            cfg = GeneratorConfig(
                seed=20261022,
                shipment_count=len(SCENARIO_TYPES),
                container_count=len(SCENARIO_TYPES),
                scenario_counts={scenario: 1 for scenario in SCENARIO_TYPES},
                products=(
                    ProductSpec("Test", "cold_chain", Decimal("2"), Decimal("8"), 30),
                ),
                sampling_interval_minutes=5,
                min_trip_days=2,
                max_trip_days=2,
            )
            report = run_verification(db_path, out_dir, log_path, config=cfg)
            self.assertEqual(report["status"], "completed")
            self.assertTrue(report["artifacts"]["passed"])
            self.assertTrue(report["evaluation"]["available"])


if __name__ == "__main__":
    unittest.main()
