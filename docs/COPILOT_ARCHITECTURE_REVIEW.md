# YottaFlex Documentation Understanding and Architecture Review

## A. Documentation inventory

### Documents successfully read

All ten expected Markdown documents were present and read in full:

1. [00_README_AND_COPILOT_GUIDE.md](./00_README_AND_COPILOT_GUIDE.md)
2. [01_PRD.md](./01_PRD.md)
3. [02_FUNCTIONAL_REQUIREMENTS.md](./02_FUNCTIONAL_REQUIREMENTS.md)
4. [03_DATA_MODEL_AND_DICTIONARY.md](./03_DATA_MODEL_AND_DICTIONARY.md)
5. [04_SYNTHETIC_DATA_SPEC.md](./04_SYNTHETIC_DATA_SPEC.md)
6. [05_BUSINESS_RULES_AND_EVALUATION.md](./05_BUSINESS_RULES_AND_EVALUATION.md)
7. [06_TECHNICAL_ARCHITECTURE.md](./06_TECHNICAL_ARCHITECTURE.md)
8. [07_API_CONTRACT.md](./07_API_CONTRACT.md)
9. [08_UI_AND_AI_FEATURE_SPEC.md](./08_UI_AND_AI_FEATURE_SPEC.md)
10. [09_TEST_PLAN_AND_DELIVERY.md](./09_TEST_PLAN_AND_DELIVERY.md)

### Missing documents

None of the expected documents are missing.

### Additional documents

No additional project documents were found in the workspace. The workspace contained the `docs/` directory and the ten documentation files listed above when the review was performed.

---

## B. Product and end-to-end workflow

### Business problem

YottaFlex is a cold-chain shipment monitoring and excursion evidence platform.

The system addresses situations where product temperature or humidity may drift outside product-specific limits during transport. Monitoring is complicated by:

- Missing sensor readings.
- Sensor calibration failures or expired calibration.
- Physically invalid sensor values.
- Route delays.
- Incorrect shipment lifecycle events.
- Incorrect or outdated threshold policies.
- Difficulty distinguishing a real excursion from insufficient evidence.
- The need for an auditable record of decisions, evidence, custody, and corrective actions.

The application must use synthetic data only. It must generate reproducible shipments, telemetry, anomalies, operational events, validation results, evaluation labels, and exports.

The deterministic monitoring engine is authoritative. Optional AI may explain incidents but must not decide whether an excursion occurred or change operational records.

### Users

The users described in `01_PRD.md`, section **Users and needs**, are:

| Role | Primary needs |
|---|---|
| Plant operator | Shipment status, sensor health, route delays, open alerts, and recording handovers or operational events |
| Maintenance/quality engineer | Excursion evidence, calibration state, reading gaps, policy details, corrective actions, and audit history |
| Production planner | Shipment progress, delivery risk, delays, and shipment-level summaries |
| OT/IT administrator | Data-generation configuration, validation status, system health, and reproducible exports |

### End-to-end workflow

1. **Configure generation**
   - An administrator selects the seed, dataset scale, trip duration, sampling interval, scenario proportions, and related settings.
   - Configuration is validated before generation.

2. **Generate master data**
   - Products are generated first.
   - Threshold policies are generated with effective dates and product associations.

3. **Generate shipment infrastructure**
   - Shipments, containers, sensors, and route stops are generated.
   - Foreign keys and lifecycle relationships must resolve.

4. **Generate monitoring schedules**
   - Sensor assignments and expected reading schedules are created.
   - Timestamps must be timezone-aware and deterministic.

5. **Generate telemetry**
   - Normal temperature and humidity values are generated using bounded, temporally correlated variation.
   - Sampling follows the configured interval unless a dropout scenario removes observations.

6. **Inject controlled scenarios**
   - Normal trips, brief excursions, prolonged excursions, missing-reading intervals, calibration failures, delays, and deliberate malformed cases are introduced.
   - Each scenario receives an identifier.

7. **Generate operational records**
   - Derived excursions, data-quality findings, custody events, notifications or alerts, and corrective actions are created from operational data.

8. **Store ground truth separately**
   - Expected detector outcomes and anomaly classifications are written to a separate ground-truth artifact or table.
   - The detection engine must not read ground truth.

9. **Validate and reconcile**
   - PK/FK integrity, enum validity, duplicate readings, expected-versus-observed intervals, chronology, policy consistency, durations, row counts, and checksums are checked.

10. **Run deterministic monitoring**
    - The engine selects the applicable threshold policy by product and event time.
    - It evaluates reading validity separately from product compliance.
    - It groups valid violating readings into excursions and calculates status, severity, duration, and evidence references.

11. **Expose API and UI**
    - Users search shipments, inspect details and evidence, review gaps and incidents, create corrective actions, view quality summaries, and export data.

12. **Evaluate**
    - Detector results are compared with separate labels.
    - Confusion-matrix counts, precision, recall, F1, policy-selection accuracy, duration error, and gap-detection results are reported.

---

## C. Data model and relationship summary

The core model is defined in `03_DATA_MODEL_AND_DICTIONARY.md`, section **Entity inventory**.

### Ten core entities

| Entity | Purpose | Important relationships |
|---|---|---|
| `Product` | Monitored product definition | Has many shipments and threshold policies |
| `ThresholdPolicy` | Product temperature/humidity limits and excursion duration limit | Belongs to a product; referenced by excursions |
| `Shipment` | Transported product journey | Belongs to a product; has containers, route stops, custody events, and excursions |
| `Container` | Physical shipment container | Belongs to a shipment; has sensors |
| `Sensor` | Temperature or humidity monitoring device | Belongs to a container; has readings and may support excursions |
| `SensorReading` | Timestamped sensor observation | Belongs to a sensor |
| `RouteStop` | Planned/actual journey location event | Belongs to a shipment |
| `Excursion` | Deterministically detected product-policy violation | References shipment, sensor, policy, evidence, and corrective actions |
| `CustodyEvent` | Append-only handover, dispatch, or receipt event | Belongs to a shipment |
| `CorrectiveAction` | Human review or remediation associated with an excursion | Belongs to an excursion |

### Relationships

The documented cardinalities are:

- Product `1:N` Shipment.
- Product `1:N` ThresholdPolicy.
- Shipment `1:N` Container.
- Shipment `1:N` RouteStop.
- Shipment `1:N` CustodyEvent.
- Container `1:N` Sensor.
- Sensor `1:N` SensorReading.
- Shipment `1:N` Excursion.
- Sensor `1:N` Excursion.
- ThresholdPolicy `1:N` Excursion.
- Excursion `1:N` CorrectiveAction.

### Important integrity rules

- All primary keys are immutable strings with documented prefixes and zero-padding.
- Timestamps must be timezone-aware.
- APIs serialize timestamps as ISO 8601 UTC.
- Measured values and policy limits should use decimal/numeric types.
- Enums or constrained strings should be used for statuses and lifecycle values.
- Foreign keys must be enforced.
- Duplicate `(sensor_id, recorded_at)` readings are prohibited except in deliberately labelled anomaly data.
- Route-stop sequence numbers must be unique within a shipment.
- Corrective-action completion cannot precede creation.
- Actual delivery cannot precede actual departure.
- A referenced excursion sensor must belong to a container assigned to that shipment.
- A referenced threshold policy must apply to the shipment's product at the relevant event time.
- Historical readings, custody events, excursions, and corrective actions must be append-only or audit-preserving.

### Recommended extension entities

The documentation permits clearly documented extensions:

- `DataQualityIssue`
- `Notification`
- `SensorAssignment`
- `ExcursionEvidence`

`ExcursionEvidence` is particularly important because one excursion may cite multiple readings and a reading may support multiple findings. The documentation recommends an explicit bridge table rather than embedding evidence IDs in a single field.

---

## D. Requirements and business rules

### Mandatory functional requirements

The P0 requirements are FR-01 through FR-10, FR-12, and FR-13 from `02_FUNCTIONAL_REQUIREMENTS.md`:

1. Configuration validation.
2. Master-data generation.
3. Dependent-record generation.
4. Synthetic telemetry.
5. Controlled scenario injection.
6. Deterministic excursion detection.
7. Gap and data-quality detection.
8. Route and lifecycle validation.
9. Custody and corrective actions.
10. REST API.
11. Export and provenance.
12. Evaluation against separate ground truth.

P1 is the basic UI.

P2 is the optional AI incident explanation feature.

### Synthetic-data requirements

From `04_SYNTHETIC_DATA_SPEC.md`:

- Default example seed: `20261022`.
- Smoke-test shipment count: `10`.
- Baseline shipment count: `1000`.
- Baseline container count: `300`.
- Sampling interval: `5` minutes.
- Journey duration: `2–5` days.
- Use a local seeded random generator.
- Do not use global uncontrolled randomness.
- Use timezone-aware timestamps.
- Use deterministic ID construction.
- Generate records in dependency order.
- Report actual generated counts rather than assuming them.
- Produce CSV per core entity.
- Produce JSON equivalents where practical.
- Produce:
  - `ground_truth.json`.
  - `generation_config.json`.
  - `source_manifest.json`.
  - `validation_summary.json`.
  - Optional SQL seed/import file.
- Include `data_origin: synthetic`.
- Include generator version, seed, timestamp, parameters, and schema/version metadata.
- Normalize volatile fields before reproducibility checksum comparison.

### Business rules

#### Policy selection

From `05_BUSINESS_RULES_AND_EVALUATION.md`, **Rule 1 — Policy selection**:

- Select the threshold policy for the shipment's product that is effective at the reading or event time.
- Do not select policies based only on convenient numeric limits.
- Store `policy_id` and version on every excursion decision.

#### Reading quality versus product compliance

These are separate decisions:

1. Is the value physically and technically plausible and trustworthy?
2. Does a valid value violate the product's policy?

A physically invalid reading:

- Creates a data-quality finding.
- Is preserved as evidence.
- Does not automatically become a confirmed product-temperature excursion.

#### Threshold comparison

The recommended default is:

- Values `< min_temp_c` violate.
- Values `> max_temp_c` violate.
- Values exactly equal to either boundary are compliant.

This behavior must be configurable only if the configuration is explicitly documented and tested.

#### Excursion grouping and duration

The recommended first implementation convention is:

- Start at the first violating reading timestamp.
- End at the first subsequent compliant reading timestamp.
- Duration is `end - start`.
- If no recovery reading exists, keep the excursion open and do not treat its duration as final.
- If a gap occurs inside the suspected excursion window, mark evidence incomplete.
- Do not assume the product was safe during the gap.
- Do not use ground truth to calculate duration.

#### Missing intervals

A missing expected reading is not a normal reading.

The system must distinguish:

- No observation received.
- Invalid observation received.
- Valid observation outside product policy.

Missing intervals must be detected independently from excursion detection.

#### Calibration

If calibration is expired or sensor status is faulty/inactive:

- Flag readings as suspect or invalid according to a documented policy.
- Preserve raw observations.
- Do not silently discard the data.

#### Route and lifecycle

Validate:

- Actual departure `<=` actual delivery.
- Planned departure `<=` planned delivery.
- Route-stop sequence.
- Custody chronology.
- State transitions.

Deliberately invalid records, such as delivery before departure, must be preserved and flagged rather than silently corrected.

#### Severity and corrective action

A simple documented severity rule is allowed:

- `critical` if excursion duration exceeds `max_excursion_minutes`.
- Otherwise `warning` or review-required.

Product release/disposal remains a human decision.

Corrective actions are new records. Resolving an excursion must not delete or overwrite the incident or its evidence.

#### Traceability

Every excursion should preserve:

- Shipment.
- Sensor.
- Applied policy and version.
- Start and end timestamps.
- Calculated duration.
- Deterministic reason.
- Evidence reading references.
- Data-quality or calibration warnings.

### Evaluation requirements

The evaluation unit must be explicitly defined before calculating metrics. The documentation suggests scenario-case or excursion-window evaluation, but it does not prescribe one final choice.

Required outputs include:

- TP, FP, FN, TN where meaningful.
- Precision.
- Recall.
- F1.
- Data-gap detection recall.
- Data-gap false-positive count.
- Policy-selection accuracy.
- Duration absolute error.
- PK/FK violations.
- Duplicate count.
- Invalid enum count.
- Chronology violations.
- Reproducibility status and row counts.

Reading-level and incident-level metrics must not be mixed.

### API requirements

The API contract in `07_API_CONTRACT.md` requires:

- `/api` route prefix.
- ISO 8601 UTC timestamps.
- Pydantic request and response models.
- Dataset generation.
- Shipment listing and detail.
- Shipment summaries.
- Excursion listing and detail.
- Corrective-action creation.
- Validation.
- Quality summary.
- Export.
- Consistent error responses.
- Pagination on list endpoints.
- 404 for missing identifiers.
- 400, 409, 422, and 500 behavior as appropriate.
- No arbitrary filesystem paths in API requests.
- No stack traces or credentials in responses.

### UI requirements

The UI requirements in `08_UI_AND_AI_FEATURE_SPEC.md` include:

- Shipment totals and status counts.
- Open excursions by severity.
- Data-quality issues and missing gaps.
- Calibration problems.
- Open corrective actions.
- Route delays.
- Latest generation and validation status.
- Search and filtering.
- Shipment journey timelines.
- Sensor readings with policy bounds.
- Clear distinction between gaps, invalid readings, and valid out-of-policy readings.
- Excursion evidence and policy version.
- Corrective-action history.
- Loading, error, retry, and empty states.
- Visible units and timezone-aware timestamps.
- Synthetic-data banner.
- Severity must not be conveyed by color alone.
- UI metrics must come from persisted API data, not hard-coded values.

### Optional AI requirements

The AI assistant is explicitly optional and must be implemented only after the deterministic core passes.

It may:

- Summarize an incident.
- Cite evidence by record ID and timestamp.
- Identify unknown or uncertain information.
- Suggest a human investigation checklist.
- Reference approved procedures.

It must not:

- Decide whether an excursion occurred.
- Modify database records.
- Receive ground-truth labels.
- Assert unsupported causes.
- Hide incomplete evidence.
- Break core monitoring if the provider is unavailable.

---

## E. Conflicts, gaps, ambiguities, assumptions, and decisions requiring approval

### 1. Excursion duration is not fully specified

The documents recommend first-violation to first-recovery duration, but several details remain unresolved:

- Does one violating reading followed by a compliant reading count as a five-minute excursion?
- If readings are sampled every five minutes, is a single violating observation considered to occupy the following interval, the preceding interval, or only an instantaneous point?
- Does `max_excursion_minutes` classify an excursion when duration is exactly equal to the threshold, or only when it is greater?
- If the last reading is violating and no recovery exists, should the duration be `NULL`, elapsed time until evaluation, or an explicitly open-ended duration?
- Does a gap terminate an excursion group, or can the engine maintain a suspected incident across the gap?
- If the gap is within an otherwise continuous violation window, should the result be one incomplete excursion or multiple excursions?

**Recommended decision:** adopt the documented convention exactly, use `duration_minutes = NULL` for unrecovered excursions, and treat any gap inside a suspected window as an evidence-incomplete condition that prevents the engine from claiming continuous safety. Explicitly test equality and gap-boundary behavior.

### 2. Threshold-boundary behavior needs formal configuration semantics

The recommended rule says equality is compliant, but the documentation also says comparison behavior may be configurable.

Unresolved points:

- Is boundary behavior globally configured, product-specific, or policy-version-specific?
- Is the comparison mode persisted as part of the threshold policy?
- How are decimal precision and rounding handled?
- Are values compared in their stored precision or after unit conversion/rounding?

**Recommended decision:** make inclusive/exclusive behavior a versioned policy attribute or a single validated system setting, use exact decimal comparison, and record the applied comparison mode in the decision evidence.

### 3. Sensor model versus sensor-count assumptions

The README assumptions say the first version assigns each sensor to one container and each container to one shipment. The data model allows:

- Container `1:N` Sensor.
- Sensor `1:N` SensorReading.
- Sensor type of either temperature or humidity.

The generator examples and API response imply sensor counts may sometimes equal container counts, but this is not a strict model requirement.

Unresolved points:

- Does every container require one temperature sensor?
- Does every container require a humidity sensor?
- Can a container have multiple temperature sensors?
- Can a shipment contain containers with different sensor configurations?
- Is a sensor reusable across shipments in v1?

**Recommended decision:** define a minimum v1 assignment rule, such as at least one active temperature sensor per container and optional humidity sensors, while retaining the relational model's ability to support multiple sensors.

### 4. Humidity evaluation is conditional

Humidity is generated and displayed, but only evaluated when a policy defines humidity limits.

Unresolved points:

- Should a humidity sensor be required when no humidity policy exists?
- What happens when a humidity policy exists but the humidity sensor is missing?
- Does a humidity violation create an `Excursion`, a separate quality issue, or both?
- Does `max_excursion_minutes` apply equally to temperature and humidity excursions?

**Recommended decision:** define whether excursions are metric-specific and whether temperature and humidity can produce separate incidents. Missing humidity data should be a data-quality issue, not automatic compliance.

### 5. Notification is mentioned but not a core entity

The PRD workflow mentions linked notifications/incidents. However:

- `Notification` is not one of the ten core entities.
- The data model permits a persisted alert record or event log.
- The API contract does not define notification endpoints.

**Recommended decision:** implement notifications as a documented extension only if needed for the UI. Prefer a persisted alert/event record linked to the excursion, with explicit lifecycle and deduplication rules.

### 6. Ground-truth storage boundary needs enforcement

The documentation consistently states that ground truth must be separate, but the exact implementation boundary is open:

- Separate JSON files.
- Separate database table.
- Separate schema or database.
- Separate evaluation-only input directory.

The system must prevent accidental loading by the detection engine and prevent exposure as detector features.

**Recommended decision:** store ground truth in a separate evaluation artifact/table with a repository-layer boundary that operational services cannot access. Add a test proving the detection engine produces the same result when ground-truth artifacts are absent.

### 7. Evaluation unit is unresolved

The evaluation document explicitly says to define the evaluation unit, for example:

- Scenario case.
- Excursion window.
- Reading.
- Shipment.

It also warns against mixing reading-level and incident-level metrics.

**Recommended decision:** use scenario-case or incident-window evaluation for primary excursion metrics, and report reading-level metrics separately only for data-quality checks.

### 8. Scenario proportions are under-specified

The system must support scenario proportions or explicit scenario counts, but no canonical default proportions are provided.

Unresolved points:

- Required default proportions.
- Whether proportions must sum exactly to 100%.
- Whether rounding can create zero-count scenarios.
- Whether every required edge case must appear in every small smoke-test run.
- Whether scenario injection is stratified by shipment, container, or sensor.

**Recommended decision:** define validated defaults and support explicit counts for deterministic test fixtures. Ensure required edge cases can be requested directly, independent of random proportions.

### 9. Route delay semantics are incomplete

Route delays are required, but the documents do not fully define:

- Which timestamps change when a delay is injected.
- Whether delays affect planned dates, actual dates, route stops, or shipment status.
- Whether delay duration is derived from route-stop records.
- Whether an arrival delay automatically creates an alert or corrective action.

**Recommended decision:** derive actual route-stop and delivery times from planned times plus delay values, preserve both planned and actual timestamps, and define the exact delay detection rule.

### 10. Invalid physical ranges are not specified

The documents require physically implausible-value detection but do not define the valid physical ranges.

Examples requiring explicit values:

- Minimum and maximum physically plausible temperature.
- Minimum and maximum humidity.
- Whether values outside a physical range are `invalid` or `suspect`.
- Whether a physically invalid reading can participate in an excursion window.
- Whether unit mismatch is a validation error or a reading-quality issue.

**Recommended decision:** define configurable physical ranges by sensor type and treat values outside them as invalid for compliance evaluation while preserving them for audit evidence.

### 11. Calibration semantics are incomplete

The model includes `calibrated_at`, `calibration_due_at`, and sensor status, but does not state:

- Whether readings after `calibration_due_at` are invalid or suspect.
- Whether calibration validity is evaluated at `recorded_at` or processing time.
- Whether a faulty sensor can return valid readings.
- Whether calibration failure is a scenario at the sensor level or reading level.

**Recommended decision:** evaluate calibration at reading time, preserve raw readings, and make the suspect/invalid policy explicit.

### 12. Shipment and container cardinality conflict

The data dictionary states `Shipment 1:N Container`, while the generator API example permits `container_count` lower than `shipment_count`:

```json
shipment_count: 10
container_count: 5
```

This is not necessarily invalid, but it means some shipments may have no containers unless generation enforces a different allocation.

Unresolved point:

- Must every shipment have at least one container?

**Recommended decision:** require at least one container per shipment for operationally monitorable shipments, or explicitly support uncontainerized shipment records and define their valid states.

### 13. Database and local-test compatibility

The technical architecture recommends PostgreSQL and permits SQLite for fast local tests if behavior remains compatible.

Potential incompatibilities include:

- Decimal handling.
- Timezone-aware datetime behavior.
- Foreign-key enforcement.
- Enum enforcement.
- Migration behavior.
- Unique constraints and partial indexes.

**Recommended decision:** use PostgreSQL as the reference database and add SQLite only after compatibility tests demonstrate equivalent behavior for the required constraints and rules.

### 14. API generation concurrency and run lifecycle

The API says duplicate generation must be prevented or a replace/new-run option must be documented. However, the run model is not defined.

Unresolved points:

- Is a generation run persisted?
- Can two generation requests run concurrently?
- Is `run_id` linked to every generated entity?
- Can a run be deleted or replaced?
- What happens after a partially failed generation?

**Recommended decision:** introduce a persisted generation-run concept or transaction boundary with an explicit run status such as `pending`, `completed`, and `failed`.

### 15. Export semantics need clarification

The export endpoint allows known datasets/artifacts, but the exact allowlist is not defined.

Potential datasets include:

- Core entities.
- Ground truth.
- Validation summary.
- Evaluation report.
- Configuration.
- Source manifest.

Unresolved points:

- Whether ground truth export is available through the normal operational API.
- Whether exports are scoped by `run_id`.
- Whether CSV and JSON must both be supported for every artifact.
- Whether volatile metadata is included.

**Recommended decision:** define a fixed export registry and require a dataset/run identifier. Consider restricting ground-truth export to an explicit evaluation/admin operation.

### 16. Security and access control are intentionally minimal but incomplete

The documentation requires:

- Environment-based secrets.
- Restricted CORS.
- No arbitrary filesystem paths.
- No stack traces or credentials in responses.

It does not define:

- Authentication.
- Authorization by role.
- Audit-user identity.
- Rate limits.
- API-level protection for generation and corrective-action endpoints.

**Recommended decision:** document authentication as out of scope for the challenge if it will not be implemented. Still apply input validation, safe errors, allowlists, and role-compatible fields.

### Mandatory versus optional requirements

#### Mandatory core

- Deterministic seeded generator.
- Ten core entities and relational integrity.
- Data-quality validation.
- Policy-aware deterministic monitoring.
- Excursion and gap detection.
- Ground-truth separation.
- Evaluation metrics.
- Persistence.
- REST API.
- Exports and provenance.
- Automated tests.
- Reproducible README workflow.
- Basic security safeguards.
- UI data must be API-backed if the UI is included in the P1 delivery.

#### Optional or lower priority

- Basic UI is P1.
- AI explanation assistant is P2.
- PostgreSQL is the reference database; SQLite is optional for local tests.
- Pandas is optional.
- JSON equivalents are practical but not strictly mandatory if CSV and required artifacts are available.
- Notification and evidence bridge tables are extensions, although evidence traceability is functionally required.

---

## F. Recommended modular architecture and module dependency order

A modular monolith is appropriate. The documentation explicitly recommends avoiding microservices for the 72-hour challenge.

### Proposed dependency layers

```text
Configuration
    ↓
Domain types and policies
    ↓
Persistence models and repositories
    ↓
Synthetic generation
    ↓
Validation and data-quality services
    ↓
Deterministic monitoring engine
    ↓
Evaluation and reporting
    ↓
Event/custody/corrective-action services
    ↓
API layer
    ↓
Frontend
    ↓
Optional AI evidence assistant
```

### Recommended implementation sequence

#### 1. Project foundation

Responsibilities:

- Settings and environment configuration.
- Validated generation configuration.
- UTC/timezone utilities.
- Logging.
- Error taxonomy.
- API-safe error handling.
- Version metadata.
- Seeded random-generator abstraction.

Dependencies: standard library and Pydantic settings/configuration.

Acceptance criteria:

- Invalid configuration fails clearly.
- Secrets are environment-based.
- Default settings are documented.
- Seeded random generation is isolated from global randomness.
- UTC serialization is consistent.
- Tests cover invalid ranges, contradictory settings, missing secrets where applicable, and deterministic configuration parsing.

#### 2. Domain models and database schema

Responsibilities:

- Domain enums.
- ORM models.
- Constraints and indexes.
- Migrations.
- Optional `GenerationRun`, `DataQualityIssue`, `Notification`, and `ExcursionEvidence` extensions.

Dependencies: foundation.

Acceptance criteria:

- All ten entities can be persisted.
- PK/FK/unique constraints work.
- Invalid lifecycle relationships are rejected or reported according to the design.
- Decimal and timezone behavior is verified.
- Migrations create the expected schema.

#### 3. Synthetic-data generator

Responsibilities:

- Master data.
- Shipment timelines.
- Containers and sensors.
- Route stops.
- Expected schedules.
- Normal telemetry.
- Scenario injection.
- Ground truth.
- Provenance artifacts.

Dependencies: foundation and domain/persistence layers.

Acceptance criteria:

- Generation order is respected.
- Same seed/config produces identical logical outputs.
- Every intentional scenario has a traceable scenario ID.
- No orphan records are created.
- Ground truth is separate from operational records.
- Smoke and baseline scale configurations are supported.

#### 4. Data validation and quality checks

Responsibilities:

- Structural validation.
- PK/FK validation.
- Enum and unit validation.
- Duplicate readings.
- Expected-versus-observed intervals.
- Physical range checks.
- Calibration checks.
- Chronology and lifecycle checks.
- Policy/product consistency.
- Reconciliation reports.

Dependencies: domain models and generated data.

Acceptance criteria:

- Deliberate invalid cases are reported with specific issue types.
- Missing readings are not filled silently.
- Validation results contain counts and bounded examples.
- Validation does not mutate source records.

#### 5. Deterministic monitoring and excursion engine

Responsibilities:

- Policy selection.
- Reading-quality assessment.
- Threshold evaluation.
- Gap-aware grouping.
- Duration calculation.
- Severity and status.
- Evidence references.
- Decision reason.

Dependencies: domain models, validation utilities, persisted source data.

Acceptance criteria:

- Ground truth is not imported.
- Boundary behavior is covered.
- Brief, prolonged, recovered, unrecovered, and gap-interrupted cases are covered.
- Expired calibration and invalid physical readings are handled separately from policy violations.
- Every decision identifies the policy version and evidence records.

#### 6. Event, custody, notification, and corrective-action services

Responsibilities:

- Custody chronology.
- Incident/notification records if implemented.
- Corrective-action creation and status transitions.
- Append-only history.

Dependencies: excursion engine and persistence.

Acceptance criteria:

- Unknown excursions cannot receive actions.
- Corrective actions preserve the original incident.
- Invalid lifecycle transitions are rejected.
- Events remain auditable.

#### 7. Evaluation and ground-truth comparison

Responsibilities:

- Load evaluation labels through a separate interface.
- Define and enforce the evaluation unit.
- Compute metrics.
- Compare durations.
- Report gap detection and policy-selection accuracy.
- Produce evaluation artifacts.

Dependencies: detection output and evaluation-only ground truth.

Acceptance criteria:

- Operational detection can run without ground truth.
- Metrics use documented denominators.
- Reading-level and incident-level metrics are not mixed.
- Reproducibility and validation results are included.

#### 8. API layer

Responsibilities:

- FastAPI application.
- Pydantic request/response models.
- Pagination.
- Generation, validation, search, detail, summary, actions, quality, and export endpoints.
- Consistent error handling.

Dependencies: all core services.

Acceptance criteria:

- API responses conform to schemas.
- Missing IDs return 404.
- Invalid input returns useful 4xx responses.
- Metrics are derived from persisted data.
- Export datasets use an allowlist.
- Arbitrary paths are rejected.

#### 9. Frontend and dashboard

Responsibilities:

- Dashboard.
- Shipment list and detail.
- Excursion detail.
- Evidence visualization.
- Gaps, calibration, custody, delays, and corrective actions.
- Loading/error/empty states.

Dependencies: API layer.

Acceptance criteria:

- No production metrics are hard-coded.
- Severity is not conveyed by color alone.
- Units and timezones are visible.
- Missing, invalid, and out-of-policy readings are visually distinct.
- Synthetic-data status is visible.

#### 10. Optional evidence-grounded AI assistant

Responsibilities:

- Retrieve structured incident evidence.
- Optionally retrieve approved SOP content.
- Generate evidence-cited explanations.
- Abstain when evidence is insufficient.
- Gracefully degrade on provider errors.

Dependencies: completed deterministic core and API.

Acceptance criteria:

- AI cannot modify records.
- Ground truth is excluded.
- Every factual statement has a source reference.
- Provider failures do not affect monitoring.
- Prompt-injection, contradictory-record, insufficient-evidence, and fabricated-ID tests pass.

---

## G. Proposed project folder structure

This follows `06_TECHNICAL_ARCHITECTURE.md`, section **Suggested repository layout**, with additions for explicit evaluation and domain boundaries.

```text
YottaFlex/
├── README.md
├── .env.example
├── pyproject.toml
├── docker-compose.yml
├── docs/
│   ├── 00_README_AND_COPILOT_GUIDE.md
│   ├── 01_PRD.md
│   ├── 02_FUNCTIONAL_REQUIREMENTS.md
│   ├── 03_DATA_MODEL_AND_DICTIONARY.md
│   ├── 04_SYNTHETIC_DATA_SPEC.md
│   ├── 05_BUSINESS_RULES_AND_EVALUATION.md
│   ├── 06_TECHNICAL_ARCHITECTURE.md
│   ├── 07_API_CONTRACT.md
│   ├── 08_UI_AND_AI_FEATURE_SPEC.md
│   ├── 09_TEST_PLAN_AND_DELIVERY.md
│   └── COPILOT_ARCHITECTURE_REVIEW.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── errors.py
│   │   │   ├── logging.py
│   │   │   └── time.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── migrations/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── repositories/
│   │   ├── domain/
│   │   │   ├── policies.py
│   │   │   ├── enums.py
│   │   │   └── identifiers.py
│   │   ├── services/
│   │   │   ├── generator.py
│   │   │   ├── scenario_injector.py
│   │   │   ├── validator.py
│   │   │   ├── excursion_engine.py
│   │   │   ├── evaluator.py
│   │   │   ├── action_service.py
│   │   │   ├── custody_service.py
│   │   │   └── export_service.py
│   │   └── api/
│   │       └── routes/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── api/
│       └── fixtures/
├── frontend/
├── data/
│   ├── generated/
│   ├── ground_truth/
│   └── reports/
└── scripts/
    ├── generate_data.py
    ├── validate_data.py
    └── evaluate.py
```

### Recommended boundaries

- `domain/` contains policy and business concepts, not HTTP concerns.
- `services/` contains workflows and business operations.
- `repositories/` isolates persistence.
- `schemas/` contains API contracts separate from ORM models.
- `data/ground_truth/` is physically and logically separate from operational generated data.
- `api/routes/` should orchestrate services only and should not contain threshold or duration rules.
- `frontend/` consumes API data and must not duplicate business logic.

---

## H. Reliability, security, and data-integrity risks

| Risk | Preventive control |
|---|---|
| Duplicate IDs | Deterministic ID generation and uniqueness constraints |
| Orphan foreign keys | Database FK constraints and integration reconciliation |
| Wrong policy selected | Effective-date policy tests and policy/product constraints |
| Exact threshold incorrectly classified | Explicit tests for values exactly equal to minimum and maximum |
| Incorrect excursion duration | Tests for one violation, multiple violations, recovery, no recovery, and threshold equality |
| Gap treated as safe | Independent expected-schedule comparison; never synthesize normal readings |
| Invalid readings treated as product excursions | Separate physical-validity and policy-compliance stages |
| Expired calibration ignored | Reading-time calibration checks |
| Wrong unit accepted | Sensor-type/unit validation |
| Delivery before departure silently fixed | Preserve source record and emit a chronology issue |
| Route-stop order corruption | Unique sequence constraints and order validation |
| Custody chronology corruption | Append-only event validation and lifecycle checks |
| Ground truth leaks into detection | Separate storage/repository boundary and detector-without-ground-truth test |
| Evaluation denominator confusion | Explicit metric denominator and zero-denominator behavior |
| Reading-level and incident-level metrics mixed | Explicit evaluation-unit types and separate reports |
| Non-reproducible generation | Same-seed/configuration repeated-run checksums |
| Volatile metadata breaks checksums | Normalize or exclude generated-at fields |
| Required scenarios are missing | Explicit scenario counts and deterministic fixtures |
| Actual counts are hard-coded | Compare API/export counts with persisted row counts |
| Partial generation leaves corrupt data | Transactions and generation-run statuses |
| Arbitrary file access through export | Dataset allowlist; never accept arbitrary server paths |
| API leaks stack traces | Standardized safe error handling |
| Unbounded list responses | Pagination and maximum page-size validation |
| UI displays fabricated values | API contract tests and tests using zero/empty data |
| AI fabricates unsupported causes | Evidence citations, abstention rules, and insufficient-evidence tests |
| Secrets are committed or logged | Environment-based configuration, `.env.example`, secret scanning, and log review |
| SQLite/PostgreSQL behavior diverges | Constraint, timezone, decimal, and migration compatibility tests |
| Unclear access control | Explicitly document authentication scope; protect generation/action operations if exposed |
| Route delays produce inconsistent timelines | Derive actual timestamps from planned values and validate all lifecycle relationships |

---

## I. Module 1 implementation plan and acceptance criteria

The requested provisional order defines Module 1 as project foundation. The milestone list in `09_TEST_PLAN_AND_DELIVERY.md` combines foundation, models, and migrations in its first milestone, but the cleaner implementation boundary is to keep Module 1 limited to configuration and platform foundations, then implement models in Module 2.

### Module 1 scope

#### Configuration

Implement validated settings for:

- Application environment.
- Database URL.
- API host and port.
- Frontend origin/CORS.
- Random seed.
- Shipment count.
- Container count.
- Sampling interval.
- Minimum and maximum trip duration.
- Scenario proportions or explicit counts.
- Physical sensor validity ranges.
- Threshold-comparison mode if configuration-driven.
- Logging level.
- Schema/generator version.

#### Time and identity utilities

Provide:

- UTC-aware datetime handling.
- ISO 8601 serialization.
- Deterministic ID construction helpers.
- Stable timestamp normalization for reproducibility.
- Seeded local random-generator creation.

#### Logging and error handling

Provide:

- Structured logging.
- Safe API error model.
- Domain/configuration validation exceptions.
- No broad exception suppression.
- No credentials or stack traces in public errors.
- Scenario and record identifiers in diagnostic logs where available.

#### Configuration validation

Reject:

- Negative or zero counts where prohibited.
- Non-positive sampling interval.
- Minimum trip duration greater than maximum.
- Invalid scenario proportions.
- Invalid physical ranges.
- Invalid threshold-comparison modes.
- Unsupported or malformed database configuration.
- Contradictory container/shipment settings, subject to the approved cardinality decision.

### Module 1 acceptance criteria

1. A valid default configuration can be loaded.
2. Environment variables override documented defaults.
3. Invalid configuration fails with a clear, actionable error.
4. Random generation uses an isolated seeded generator.
5. Two generator instances with identical seed/configuration produce identical random sequences.
6. UTC timestamps serialize consistently.
7. Deterministic IDs follow documented prefix and formatting rules.
8. Logging does not expose secrets.
9. API-safe errors have the documented shape.
10. Unit tests cover:
    - Valid configuration.
    - Invalid numeric ranges.
    - Contradictory trip durations.
    - Invalid scenario proportions.
    - Timezone conversion.
    - ID generation.
    - Seed reproducibility.
    - Secret-safe error/log behavior.

### Module 1 should not yet implement

- Database tables or migrations.
- Synthetic shipment generation.
- Sensor readings.
- Excursion detection.
- Ground-truth evaluation.
- API business endpoints.
- Frontend.
- AI integration.

---

## J. Questions requiring decisions before implementation

### Before Module 1

1. What are the approved default scenario proportions?
2. Must scenario proportions sum exactly to 1.0 or 100%?
3. Should explicit scenario counts take precedence over proportions?
4. Which physical temperature and humidity ranges define `valid`, `suspect`, and `invalid`?
5. Is threshold equality globally inclusive, or configurable per policy?
6. What is the approved application/database timezone policy beyond API serialization as UTC?
7. Are all configuration values environment variables, API request fields, or both?
8. What are the supported maximum dataset sizes and page sizes?

### Before database schema implementation

1. Must every shipment have at least one container?
2. Must every container have a temperature sensor?
3. Are humidity sensors mandatory, optional, or determined by policy?
4. Can sensors be reused across shipments?
5. Is sensor assignment history required in v1?
6. Should `Notification`, `DataQualityIssue`, `SensorAssignment`, and `ExcursionEvidence` be implemented in the core schema?
7. How will generation runs be represented and isolated?
8. What database behavior must SQLite support if it is enabled?
9. Are database authentication and role-based permissions in scope?

### Before synthetic-data generation

1. What exact proportions or counts should be used for:
   - Normal trips.
   - Brief excursions.
   - Prolonged excursions.
   - Dropouts.
   - Calibration failures.
   - Route delays.
   - Required malformed cases?
2. Must every smoke-test generation include all five deliberate challenge cases?
3. How are scenarios assigned when there are fewer shipments than scenario types?
4. Are route delays represented by actual timestamp shifts, explicit delay fields, or both?
5. How are planned and actual route-stop times derived?
6. What is the exact sensor-to-container allocation rule?
7. What is the approved generator versioning strategy?

### Before the detection engine

1. Does a gap break an excursion group or create one incomplete group spanning the gap?
2. How is duration calculated for a single violating reading?
3. How is duration calculated when the first compliant reading is missing?
4. Is duration threshold classification `>` or `>=`?
5. Is an unrecovered excursion's duration `NULL`, provisional, or calculated to the evaluation time?
6. Can invalid or suspect readings contribute to excursion grouping?
7. Can humidity violations create excursions?
8. Are temperature and humidity incidents separate?
9. What calibration state makes a reading suspect versus invalid?
10. How are duplicate timestamps processed by the detector when duplicates are deliberately present?
11. Does the engine process only persisted records, or can it process in-memory generated records before persistence?

### Before evaluation

1. What is the primary evaluation unit: scenario case, excursion window, shipment, or another unit?
2. Should false positives and false negatives be reported at incident level, reading level, or both?
3. How are ambiguous cases with incomplete evidence labelled?
4. What is the expected detector result for each deliberate anomaly?
5. What is the accepted duration error tolerance?
6. Are TN values meaningful for the selected evaluation unit?
7. Is ground truth stored only as files, only in a database table, or both?
8. Should the operational API expose ground truth, or should it remain evaluation-only?

### Before API implementation

1. Is `/api/generate` synchronous, asynchronous, or allowed to return a pending run?
2. What happens when two generation requests overlap?
3. Is a `run_id` required on all operational entities and endpoints?
4. Is generation replaceable, append-only, or isolated per run?
5. What datasets are included in the export allowlist?
6. Is ground truth export restricted to administrator/evaluation workflows?
7. What are the exact time-window semantics for `/api/quality/summary`?
8. Which shipment-detail collections are paginated?
9. What status transitions are allowed for excursions and corrective actions?
10. Are notifications exposed through the API?

### Before UI implementation

1. Which filters are mandatory for the first UI release?
2. Should chart data be paginated or downsampled for large reading sets?
3. How should open excursions without final duration be displayed?
4. What visual convention distinguishes suspect from invalid readings?
5. Is authentication represented in the UI or explicitly out of scope?
6. What constitutes a “latest generation/validation run” when multiple runs exist?

### Before optional AI implementation

1. Which LLM provider and model are approved?
2. Which procedure or SOP documents are approved sources?
3. Is structured SQL retrieval sufficient, or is semantic retrieval required?
4. What is the maximum evidence context size?
5. What citation format is required in the UI and API?
6. What user roles may invoke the assistant?
7. What provider metadata may be logged?
8. What is the fallback response contract when the provider fails?

---

## Overall architecture recommendation

The documentation supports a modular monolith with the following priorities:

1. Configuration and reproducibility.
2. Domain models and relational constraints.
3. Synthetic generation.
4. Validation and data-quality detection.
5. Deterministic policy and excursion engine.
6. Evaluation against isolated ground truth.
7. Persistence-backed API.
8. Exports and reproducibility reporting.
9. Basic UI.
10. Optional evidence-grounded AI.

The most important decisions to resolve before coding are:

- The excursion-duration convention.
- Gap behavior.
- Evaluation unit.
- Physical validity ranges.
- Sensor/container allocation.
- Notification representation.
- Generation-run lifecycle.

This review is analysis-only. It does not implement application code, initialize Docker, install packages, or modify the original project documentation.

---

## K. Authority and source classification

This section supersedes any earlier wording in this review that could blur the distinction between requirements and recommendations.

### Official candidate submission requirements

The following requirements come from the official reference PDFs in `docs/references/`:

- [YottaFlex AI Candidate Project Submission Guidelines.pdf](./references/YottaFlex%20AI%20Candidate%20Project%20Submission%20Guidelines.pdf)
- [YottaFlex AI Candidate Project-FAQ.pdf](./references/YottaFlex%20AI%20Candidate%20Project-FAQ.pdf)

The official guidance states that:

- The challenge window is 72 hours. Artifact timestamps are used to verify the window.
- The submission should contain working, executable code and clear installation, configuration, run, and verification instructions.
- A dedicated public GitHub repository is required.
- Prompt history for every AI tool used is required.
- AI tools may be used, but the submission must remain the candidate's individual work.
- The candidate must understand and be able to explain the core logic, design choices, dependencies, and limitations.
- Any suitable technology stack may be selected, using free or locally runnable services where possible.
- A hosted demo and automated test suite are not officially mandatory, but core behavior and verification must be demonstrated clearly.
- Requirements that are unclear or incomplete may be handled with reasonable assumptions, provided assumptions, limitations, deviations, and next steps are documented.
- Secrets, credentials, personal or sensitive information, and unauthorized proprietary code must not be published.
- Standard dependencies and small illustrative snippets are acceptable; a complete existing solution must not be imported to perform the core project work.

These are official submission and candidate-conduct requirements. They are not implementation details for the cold-chain system.

### Existing project requirements

The ten original project specification documents in `docs/00_*.md` through `docs/09_*.md` define the YottaFlex application requirements. They are the source of truth for:

- The cold-chain product problem and user journeys.
- The ten core entities and relational constraints.
- Synthetic data, fixed-seed reproducibility, and provenance.
- Data quality, calibration, route, lifecycle, policy, and excursion behavior.
- Separation of operational data from ground truth.
- Evaluation metrics and test scenarios.
- The modular-monolith architecture and API/UI/AI scope.

The project documents assign priorities of P0, P1, and P2. In particular, the project test plan requires automated tests as part of the implementation baseline even though the official candidate FAQ does not mandate an automated test suite for submission. The project requirement is the applicable requirement for this implementation.

The original ten specification documents must remain unchanged.

### Proposed implementation decisions

Recommendations in this review, including proposed folder names, module boundaries, optional extension entities, specific test organization, and suggested default conventions, are architecture proposals only. They are not official YottaFlex submission requirements and must not be presented as such.

No business-specific default is finalized by this review. Shipment counts, sampling intervals, trip-duration bounds, scenario proportions, physical sensor ranges, threshold comparison, calibration behavior, and excursion policies must remain configurable and must be finalized in their relevant modules after the necessary decisions are approved.

---

## L. Refined Module 1 scope

Module 1 is limited to reusable platform infrastructure. It may implement:

- Configuration infrastructure and validated environment loading without finalizing business-specific defaults.
- Generic settings structures that allow later modules to define shipment counts, sampling intervals, trip-duration bounds, scenario proportions, sensor ranges, and excursion policies.
- UTC-aware datetime utilities and consistent ISO 8601 UTC serialization helpers.
- Structured logging infrastructure.
- Explicit configuration and application error types and safe error handling.
- Generic deterministic ID helpers only where justified by the foundation; entity-specific prefixes, formats, and lifecycle rules are finalized in Module 2.
- Isolated seeded-randomness infrastructure without defining scenario distributions or synthetic-data behavior.
- Focused unit tests for the infrastructure above.

Module 1 must not implement:

- Database models.
- Migrations.
- ORM/repository behavior.
- Synthetic-data generation.
- Scenario injection.
- Sensor or product business rules.
- Excursion detection.
- Ground-truth evaluation.
- Business API endpoints.
- Frontend code.
- AI integration.
- Docker initialization.

### Module 1 decisions required now

Only these decisions are required before Module 1:

1. Use environment loading and validated configuration infrastructure, while leaving business-specific defaults undefined or explicitly supplied by later modules.
2. Use timezone-aware UTC utilities and ISO 8601 UTC serialization as already required by the existing project documents.
3. Use structured logging and explicit error handling without exposing secrets or stack traces.
4. Use isolated seeded randomness as a reusable capability, without selecting scenario proportions or generator behavior.
5. Add generic ID helpers only if the foundation has a clear use for them; defer entity-specific ID formats to Module 2.
6. Preserve the existing repository/tooling state. Do not install dependencies or change dependency manifests without separate approval.

### Decisions deferred to dependent modules

The following decisions do not block Module 1:

- Shipment and container counts.
- Sampling interval.
- Minimum and maximum trip duration.
- Scenario proportions and explicit scenario counts.
- Physical temperature and humidity ranges.
- Product policy and threshold comparison.
- Sensor-to-container allocation.
- Humidity-sensor requirements.
- Calibration semantics.
- Excursion duration and severity.
- Gap-interrupted excursion grouping.
- Ground-truth storage and evaluation unit.
- Generation-run lifecycle.
- Database and migration design.
- API behavior.
- UI behavior.
- AI provider and retrieval design.

Module 1 acceptance is therefore based on reusable infrastructure correctness, not on unapproved domain defaults.
