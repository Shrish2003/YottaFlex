# Functional Requirements and Acceptance Criteria

## FR-01 — Configuration
The user can set random seed, shipment count, container count, journey-duration range, sampling interval, and scenario proportions.
**Acceptance:** invalid or contradictory configuration is rejected with a clear message. Defaults are documented.

## FR-02 — Master data generation
Generate Product and ThresholdPolicy first, then Shipment, Container, Sensor, and RouteStop records.
**Acceptance:** every FK resolves; policies have valid limits and effective dates; identifiers follow conventions.

## FR-03 — Dependent record generation
Generate SensorReading and operational event records only after parent records exist.
**Acceptance:** every reading references an existing sensor; reading timestamps fall within the assigned monitoring period unless a labelled test deliberately violates a rule.

## FR-04 — Synthetic telemetry
Generate temperature and humidity readings at the configured interval using a realistic baseline and bounded variation.
**Acceptance:** normal scenarios mostly remain within policy; units are explicit; timestamps and values are reproducible.

## FR-05 — Scenario injection
Support normal trips, brief excursions, prolonged excursions, sensor dropouts, calibration failures, route delays, and the five required deliberate anomaly cases documented in `05_BUSINESS_RULES_AND_EVALUATION.md`.
**Acceptance:** each injected case has a scenario ID and ground-truth label in a separate file/table that the detection engine cannot read as input.

## FR-06 — Excursion detection
Apply the product policy effective at the event time, identify consecutive violating observations, group them into excursions according to documented logic, calculate duration, and assign a rule-based severity/status.
**Acceptance:** normal, boundary, brief, prolonged, and gap-interrupted cases have unit tests. Threshold equality behavior is documented.

## FR-07 — Gap and data-quality detection
Compare expected readings with actual readings; detect missing intervals, duplicate timestamps, invalid physical ranges, suspect readings, and calibration issues.
**Acceptance:** a gap does not become a normal reading and does not count as proof that the product remained within limits.

## FR-08 — Route and lifecycle validation
Validate departure/delivery chronology, route-stop sequence, custody order, and state transitions.
**Acceptance:** valid records pass; deliberate bad records are flagged with specific issue types rather than silently corrected.

## FR-09 — Custody and corrective actions
Record custody changes and corrective actions as new records. Keep created/completed timestamps and outcomes.
**Acceptance:** resolving an excursion does not delete or overwrite the incident or its evidence.

## FR-10 — API
Expose generation, shipment search/detail, summaries, excursion list/detail, corrective-action creation, validation, and export endpoints as documented in `07_API_CONTRACT.md`.
**Acceptance:** responses conform to Pydantic response models; invalid input receives a useful 4xx response; missing IDs return 404.

## FR-11 — UI
Provide a dashboard and detail views with counts, open issues, shipment status, excursion evidence, gaps, custody history, and corrective actions.
**Acceptance:** data is fetched from the API; no core metric is hard-coded.

## FR-12 — Export and provenance
Export core entities, ground truth, validation summary, configuration, and source manifest.
**Acceptance:** export files include schema/version and synthetic-data provenance in README/manifest.

## FR-13 — Evaluation
Compare engine decisions with ground truth and report confusion matrix counts and metrics where applicable.
**Acceptance:** evaluation labels are not used by the detector; metrics are reproducible and their denominators are documented.

## FR-14 — AI incident explanation (optional stretch goal)
Provide a concise evidence-grounded explanation of a selected incident using retrieved structured records and approved procedures.
**Acceptance:** every factual statement cites record IDs/timestamps or procedure references; the model cannot modify excursion decisions; if evidence is missing, it says so; API/model failure does not break core monitoring.

## Priority
P0: FR-01 through FR-10, FR-12, FR-13 (core data and monitoring workflow).
P1: FR-11 (basic UI).
P2: FR-14 (AI enhancement), only after P0 passes.
