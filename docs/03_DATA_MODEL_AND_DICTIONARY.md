# Data Model, Relationships, and Data Dictionary

## Conventions
- All primary keys are immutable strings with documented prefixes and zero-padding.
- Store timestamps as timezone-aware values; APIs serialize ISO 8601 UTC.
- Use decimal/numeric types for measured values and threshold limits.
- Use enums or constrained strings for lifecycle and status fields.
- Add `created_at` and, where useful, `updated_at` to mutable business records.
- Preserve history for readings and events. Do not delete events to represent resolution.
- Ground truth is a separate evaluation artifact, not a feature of operational records.

## Entity inventory

### Product
- `product_id` PK, string, required, unique; example `PRD-000001`
- `name` string, required
- `category` string/enum, required
- `active` boolean, required
- Purpose: defines the monitored product.

### ThresholdPolicy
- `policy_id` PK, string, required, unique; example `POL-000001`
- `product_id` FK -> Product, required
- `min_temp_c` decimal, required
- `max_temp_c` decimal, required
- `max_excursion_minutes` integer, required, >= 0
- `min_humidity_pct` decimal, optional
- `max_humidity_pct` decimal, optional
- `effective_from` datetime, required
- `effective_to` datetime, nullable
- `version` integer, required
- Constraints: min <= max; humidity limits either both defined or neither; effective_to > effective_from if present; avoid ambiguous overlapping active policies for a product.

### Shipment
- `shipment_id` PK, string, required, unique; example `SHP-2026-000001`
- `product_id` FK -> Product, required
- `origin`, `destination` strings, required
- `planned_departure`, `planned_delivery` datetime, required
- `actual_departure`, `actual_delivery` datetime, nullable
- `status` enum: planned, in_transit, delivered, cancelled
- Constraints: actual delivery cannot precede actual departure; planned delivery should not precede planned departure.

### Container
- `container_id` PK, string, required, unique; example `CNT-000001`
- `shipment_id` FK -> Shipment, required in v1
- `container_type` string, required
- `status` enum: prepared, in_transit, delivered, quarantined
- V1 assumption: one shipment per container. If reused, create an explicit assignment-history table.

### Sensor
- `sensor_id` PK, string, required, unique; example `SNS-CNT-000001-TEMP`
- `container_id` FK -> Container, required in v1
- `sensor_type` enum: temperature, humidity, required
- `calibrated_at` datetime, required
- `calibration_due_at` datetime, required
- `status` enum: active, inactive, faulty
- Constraint: calibration_due_at should be after calibrated_at.

### SensorReading
- `reading_id` PK, string, required, unique; convention `RDG-<sensor-id>-<UTC timestamp>`
- `sensor_id` FK -> Sensor, required
- `recorded_at` datetime, required
- `value` decimal, required
- `unit` string/enum, required (`°C` for temperature; `%RH` for relative humidity)
- `quality_status` enum: valid, suspect, invalid
- `issue_type` nullable string
- Constraints: prevent duplicate `(sensor_id, recorded_at)` readings for the same sensor unless duplicates are intentionally generated as a labelled anomaly.

### RouteStop
- `route_stop_id` PK, string, required, unique; example `RST-000001`
- `shipment_id` FK -> Shipment, required
- `sequence_number` integer, required
- `location` string, required
- `planned_arrival` datetime, required
- `actual_arrival`, `actual_departure` datetime, nullable
- `status` enum: planned, arrived, departed, skipped
- Constraint: unique `(shipment_id, sequence_number)`.

### Excursion
- `excursion_id` PK, string, required, unique; example `EXC-2026-000001`
- `shipment_id` FK -> Shipment, required
- `sensor_id` FK -> Sensor, required
- `policy_id` FK -> ThresholdPolicy, required
- `started_at` datetime, required
- `ended_at` datetime, nullable while open
- `duration_minutes` integer, nullable while unresolved or not calculable
- `severity` enum: warning, critical
- `status` enum: open, under_review, resolved
- `decision_reason` string, required
- Constraint: the referenced sensor must belong to a container assigned to the shipment; policy must apply to the shipment's product and event time.

### CustodyEvent
- `custody_event_id` PK, string, required, unique; example `CUS-000001`
- `shipment_id` FK -> Shipment, required
- `event_time` datetime, required
- `event_type` enum: handover, received, dispatched
- `from_party` string, nullable
- `to_party` string, required
- `location` string, required
- `evidence_ref` string, nullable
- Append-only event history.

### CorrectiveAction
- `action_id` PK, string, required, unique; example `ACT-000001`
- `excursion_id` FK -> Excursion, required
- `assigned_to` string, required
- `action_type` enum: inspect, quarantine, recalibrate, review, other
- `description` string, required
- `created_at` datetime, required
- `completed_at` datetime, nullable
- `status` enum: open, in_progress, completed, cancelled
- `outcome` string, nullable
- Constraint: completed_at cannot precede created_at.

## Relationships / cardinality
- Product 1:N Shipment
- Product 1:N ThresholdPolicy
- Shipment 1:N Container (v1)
- Shipment 1:N RouteStop
- Shipment 1:N CustodyEvent
- Container 1:N Sensor (v1)
- Sensor 1:N SensorReading
- Shipment 1:N Excursion
- Sensor 1:N Excursion
- ThresholdPolicy 1:N Excursion
- Excursion 1:N CorrectiveAction

## Implementation notes
- The 10 entities above are the challenge's core entities. `DataQualityIssue`, `Notification`, and `SensorAssignment` may be added as clearly documented extensions if time allows.
- The challenge mentions notifications; these can initially be represented by persisted alert records or an event log. If a Notification table is added, document its FK and lifecycle.
- An excursion should preserve links to the readings that justify it. Prefer an explicit `ExcursionEvidence` bridge table if one excursion can cite multiple readings and one reading may support multiple findings.
- Do not use ground-truth labels in production detection logic.
