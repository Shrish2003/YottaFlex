# Product Requirements Document (PRD)
## Product: Cold-Chain Shipment Monitoring and Excursion Evidence Platform
**Version:** 1.0 draft  
**Status:** Implementation baseline for coding challenge

## 1. Product summary
Build a working end-to-end application that generates reproducible synthetic cold-chain data, monitors temperature and humidity across shipment journeys, detects excursions and data-quality exceptions, preserves an auditable evidence trail, and reports measurable outcomes.

The system is intended to demonstrate sound data modeling, deterministic business rules, traceability, exception handling, evaluation, and practical delivery. A small evidence-grounded AI investigation assistant may be included after the core workflow is reliable.

## 2. Problem statement
Storage and transport conditions can drift outside product-specific limits. Missing readings, faulty or overdue sensors, route delays, and inconsistent lifecycle events make it difficult to distinguish a real excursion from insufficient evidence. Operators and quality staff need a consistent way to detect problems, inspect supporting evidence, record actions, and evaluate whether the monitoring system made the correct decisions.

No real sensor dataset is supplied. The system must generate synthetic data using documented rules and a fixed seed. Synthetic data must be clearly identified as synthetic.

## 3. Goals
- Generate master and dependent records with consistent primary and foreign keys.
- Simulate readings at fixed intervals, initially every five minutes, over journeys lasting two to five days.
- Apply product-specific policies and effective dates.
- Detect threshold excursions and calculate durations using a documented convention.
- Detect data gaps and invalid/suspect readings without treating missing data as safe.
- Create linked notifications/incidents, custody events, and corrective actions where applicable.
- Preserve traceability from each decision to source records and the policy version used.
- Provide a dashboard/API and CSV/JSON exports.
- Evaluate detection against separate ground-truth labels and report measurable metrics.
- Ensure the generator is reproducible for a fixed seed and configuration.

## 4. Users and needs
### Plant operator
Needs a clear view of shipment status, sensor health, route delays, and open alerts; needs to record handovers or operational events.

### Maintenance/quality engineer
Needs evidence for excursions, sensor calibration status, reading gaps, policy details, corrective actions, and audit history.

### Production planner
Needs shipment progress, delivery risks, delays, and shipment-level summaries.

### OT/IT administrator
Needs data-generation configuration, validation results, system health, and reproducible exports.

## 5. Scope
### In scope
- Synthetic-data generator and fixed-seed reproducibility.
- Ten core entities: Product, Shipment, Container, Sensor, SensorReading, RouteStop, ThresholdPolicy, Excursion, CustodyEvent, CorrectiveAction.
- Relational persistence and documented schema.
- Deterministic rule engine.
- Deliberately injected, labelled edge cases.
- Data integrity and reconciliation checks.
- REST API, a basic dashboard, and CSV/JSON exports.
- Test suite and evaluation report.
- Optional evidence-grounded AI incident explanation feature, only after the deterministic core passes tests.

### Out of scope for the first version
- Real hardware or IoT device integration.
- Production deployment or regulatory certification.
- Automatic product-release or disposal decisions without human review.
- Real patient/customer personal data.
- Complex microservices, streaming infrastructure, or advanced predictive ML unless core requirements are complete.

## 6. Core user journeys
1. Administrator configures seed and dataset scale.
2. System creates master data before dependent records.
3. Generator creates journey timelines and readings at configured intervals.
4. Scenario injector introduces known anomalies and records them in separate ground truth.
5. Rule engine processes source data and creates excursions and data-quality findings.
6. User opens a shipment and sees timeline, readings, policies, route stops, custody, excursions, and actions.
7. Quality engineer records a corrective action and status changes without deleting the original event.
8. User exports datasets and reviews validation/evaluation metrics.

## 7. Product requirements
- All entities have immutable primary keys following documented conventions.
- Foreign keys and join relationships must validate.
- Derived fields must be calculated from source records, not independently randomized.
- Every excursion references the applicable policy and supporting evidence.
- Missing intervals must be flagged as data gaps; absence of readings is not evidence of safe conditions.
- Physical sensor validity and product policy compliance must be treated as separate checks.
- Lifecycle transitions and timestamps must be validated.
- Historical readings and events must not be silently overwritten.
- Ground truth must be stored separately from operational input and excluded from detection features.
- Same seed plus same configuration must reproduce the same logical dataset and row counts.
- All generated data must be labelled synthetic.

## 8. Success criteria
- Zero duplicate primary keys.
- Zero orphan foreign keys in the valid baseline dataset.
- All enumerated intentional anomaly cases are present and traceable.
- Correct policy is selected for each evaluated excursion.
- Derived durations reconcile with source readings under the documented convention.
- Missing readings are identified in expected-gap checks.
- Shipment, route, and custody timelines pass temporal validation except for labelled anomaly cases.
- Fixed-seed runs have identical logical outputs/checksums when run in the same supported environment and version.
- API and UI display results from persisted data, not hard-coded demo values.
- Automated tests pass and the README permits a reviewer to reproduce the workflow.

## 9. Risks and mitigations
- Synthetic data appears too random: use realistic baselines, bounded variation, temporal correlation, and controlled scenarios.
- Missing readings hide incidents: detect expected-time gaps independently.
- Incorrect duration logic: document the interval convention and test boundaries.
- AI fabricates causes: provide only retrieved evidence, require record references, and abstain when evidence is insufficient.
- Scope exceeds 72 hours: prioritize generator, models, rules, validation, tests, then API/UI; AI is optional until core passes.
- Dataset is large: support configurable scale and run smoke tests before full generation.

## 10. Dependencies and assumptions
Python-based backend, relational database, and a browser-based UI are assumed. External datasets are not required. Any external data must have documented provenance and an appropriate license. All time values should be timezone-aware and serialized consistently, preferably ISO 8601 UTC in APIs.

## 11. Definition of done
A fresh checkout can be configured using documented steps, generate a reproducible dataset, run the deterministic monitoring pipeline, execute tests, start the API/UI, inspect an excursion and its evidence, and export data plus a validation/evaluation summary.
