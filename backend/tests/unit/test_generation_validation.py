import unittest

from backend.app.services.detection import detect_dataset
from backend.app.services.evaluation import evaluate_ground_truth
from backend.app.services.generator import GeneratorConfig, generate_dataset
from backend.app.services.validation import validate_dataset
from backend.tests.unit.test_generator import config


class GenerationValidationTests(unittest.TestCase):
    def test_valid_dataset_passes(self) -> None:
        report = validate_dataset(generate_dataset(config()))
        self.assertTrue(report.passed, report.errors)
        self.assertEqual(report.counts["shipments"], 11)

    def test_duplicate_identifier_is_reported(self) -> None:
        dataset = generate_dataset(config())
        dataset.products.append(dataset.products[0])
        report = validate_dataset(dataset)
        self.assertIn("products contains duplicate identifiers", report.errors)

    def test_overlapping_assignment_intervals_are_rejected(self) -> None:
        dataset = generate_dataset(config())
        first, second = dataset.assignments[:2]
        second.container = first.container
        second.assigned_from = first.assigned_from
        report = validate_dataset(dataset)
        self.assertIn(
            f"container {first.container.container_id} has overlapping assignments",
            report.errors,
        )

    def test_cross_shipment_excursion_assignment_is_rejected(self) -> None:
        dataset = generate_dataset(config())
        excursion = dataset.excursions[0]
        replacement = next(
            assignment
            for assignment in dataset.assignments
            if assignment.assignment_id != excursion.assignment_id
        )
        excursion.assignment_id = replacement.assignment_id
        excursion.container_id = replacement.container_id
        report = validate_dataset(dataset)
        self.assertIn(
            f"excursion {excursion.excursion_id} crosses shipment assignments",
            report.errors,
        )

    def test_intentional_wrong_policy_is_reported_as_warning(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"wrong_product_threshold": 1},
                products=config().products,
            )
        )
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertTrue(report.passed, report.errors)
        self.assertTrue(any("intentional policy anomaly" in warning for warning in report.warnings))

    def test_unmarked_wrong_policy_is_reported_as_error(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"brief_excursion": 1},
                products=(
                    config().products[0],
                    config().products[0].__class__(
                        name="Alternate product",
                        category="cold_chain",
                        min_temp_c=config().products[0].min_temp_c,
                        max_temp_c=config().products[0].max_temp_c,
                        max_excursion_minutes=30,
                        min_humidity_pct=config().products[0].min_humidity_pct,
                        max_humidity_pct=config().products[0].max_humidity_pct,
                    ),
                ),
            )
        )
        dataset.excursions[0].policy_id = dataset.policies[1].policy_id
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("uses a policy for the wrong product" in error for error in report.errors)
        )

    def test_excursion_evidence_requires_valid_context(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"brief_excursion": 1},
                products=config().products,
            )
        )
        evidence = dataset.excursion_evidence[0]
        reading = next(item for item in dataset.readings if item.reading_id == evidence.reading_id)
        evidence.reading_id = "RDG-MISSING"
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertIn(f"evidence {evidence.evidence_id} references missing records", report.errors)

        evidence.reading_id = reading.reading_id
        evidence.excursion_id = "EXC-MISSING"
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertIn(f"evidence {evidence.evidence_id} references missing records", report.errors)

    def test_assignment_interval_boundaries_are_half_open(self) -> None:
        dataset = generate_dataset(
            GeneratorConfig(
                shipment_count=1,
                container_count=1,
                scenario_counts={"normal": 1},
                products=config().products,
            )
        )
        assignment = dataset.assignments[0]
        reading = next(iter(dataset.readings))
        reading.recorded_at = assignment.assigned_from
        self.assertTrue(validate_dataset(dataset, require_scenario_coverage=False).passed)
        reading.recorded_at = assignment.assigned_to
        report = validate_dataset(dataset, require_scenario_coverage=False)
        self.assertIn(f"reading {reading.reading_id} falls outside its assignment", report.errors)

    def test_all_11_scenarios_evaluation_metrics(self) -> None:
        dataset = generate_dataset(config())
        report = validate_dataset(dataset)
        self.assertTrue(report.passed)
        findings = detect_dataset(dataset).findings
        result = evaluate_ground_truth(dataset.ground_truth, findings)
        self.assertTrue(result.available)
        self.assertEqual(result.confusion_matrix, {"tp": 10, "fp": 0, "fn": 0, "tn": 1})
        self.assertEqual(result.metrics["precision"]["value"], 1.0)
        self.assertEqual(result.metrics["recall"]["value"], 1.0)
        self.assertEqual(result.metrics["f1"]["value"], 1.0)
        self.assertEqual(result.metrics["gap_recall"]["value"], 1.0)
        self.assertEqual(result.metrics["policy_accuracy"]["value"], 1.0)
        self.assertEqual(result.metrics["duration_absolute_error_minutes"]["value"], 0.0)


if __name__ == "__main__":
    unittest.main()
