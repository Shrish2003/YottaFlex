# Synthetic Data Generation Specification

## Objective
Generate plausible, deterministic cold-chain shipment data without relying on real sensor feeds. All generated records must be labelled synthetic.

## Configuration
Support:
- `seed` (default example: 20261022)
- `shipment_count` (smoke test: 10; baseline: 1000)
- `container_count` (baseline: 300)
- `sampling_interval_minutes` (default: 5)
- `min_trip_days` (default: 2)
- `max_trip_days` (default: 5)
- scenario proportions or explicit scenario counts
- optional start datetime and scenario profile version

Validate configuration before generation. Use a local seeded random generator, not global uncontrolled randomness.

## Generation order
1. Products.
2. Threshold policies with effective dates.
3. Shipments.
4. Containers and their shipment assignments.
5. Route stops.
6. Sensors and calibration attributes.
7. Expected reading schedule for each assigned sensor.
8. Normal synthetic telemetry.
9. Controlled scenario injection.
10. Derived excursions, gaps, custody events, and corrective actions.
11. Ground truth in a separate output.
12. Integrity and reconciliation report.

## Synthetic telemetry
- Use bounded baseline values and temporally correlated variation rather than independent arbitrary values.
- Temperature normal values should generally sit inside the assigned product's policy range with some variation.
- Humidity should use explicit units and plausible bounded values. Only evaluate humidity excursions if policy humidity limits exist.
- Simulate route stops and delays using consistent timestamps.
- Sampling should occur at the configured interval unless a dropout scenario intentionally removes observations.
- Use timezone-aware timestamps and deterministic ID construction.

## Scenario types
Include normal trips, brief temperature excursions, prolonged excursions, missing-reading intervals, sensor calibration failures, route delays, and labelled challenge edge cases:
1. Reading outside physically plausible range.
2. Missing interval incorrectly interpreted as safe.
3. Shipment delivered before departure.
4. Wrong product threshold applied.
5. Excursion duration undercounted.

For deliberate malformed records, keep the anomalous value and attach a specific `issue_type`/scenario identifier. Do not corrupt unrelated fields just to make the case fail.

## Ground truth
Write `ground_truth.json` or a separate database table. Each case should include:
- `case_id`
- entity IDs involved
- `scenario_type`
- expected detector decision
- expected issue/excursion classification
- expected policy ID where relevant
- expected duration or boundary expectation where deterministic
- short rationale
Ground truth must never be loaded by the detection engine or exposed as input features to it.

## Outputs
- CSV per core entity.
- JSON equivalents if practical.
- `ground_truth.json`.
- `generation_config.json`.
- `source_manifest.json` with `data_origin: synthetic`, generator version, seed, timestamp, parameters.
- `validation_summary.json`.
- Optional SQL seed/import file.

## Validation
- PK uniqueness and FK integrity.
- Required fields, enum values, units, and ID format.
- Duplicate `(sensor_id, recorded_at)` detection.
- Expected versus observed reading intervals.
- Chronological and lifecycle checks.
- Policy/product consistency.
- Duration reconciliation.
- Row counts and file checksums.
- Run twice with same seed and config; compare logical row counts and checksums. Avoid volatile generated-at fields in checksum inputs or normalize them first.

## Scale guidance
- Start with 10 shipments and a short journey to debug.
- Then use baseline volume: 1000 shipments, 300 containers, 2–5 day trips, five-minute readings.
- Reading count depends on number of sensors, trip lengths, and dropout injection; calculate and report actual counts rather than hard-coding expected totals.
