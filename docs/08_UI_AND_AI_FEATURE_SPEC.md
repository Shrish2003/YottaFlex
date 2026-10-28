# UI and Optional AI Investigation Assistant

## Dashboard
Show:
- total shipments and current status counts;
- open excursions by severity;
- data-quality issues and missing-reading gaps;
- overdue/failed calibration counts;
- open corrective actions;
- latest route delays;
- latest generation/validation run status.

All metrics must be fetched from API endpoints and derived from persisted data.

## Shipment list
- Search/filter by shipment ID, status, product, origin/destination, and date range.
- Show status, planned/actual delivery, excursion count, and review state.
- Provide a clear empty state and loading/error states.

## Shipment detail
- Journey timeline with departure, route stops, custody events, and delivery.
- Sensor readings plotted over time with policy bounds.
- Clearly distinguish missing intervals, invalid readings, and valid out-of-policy readings.
- Show applicable policy and version.
- Show excursions and their evidence.
- Show corrective actions and status history.

## Excursion detail
- Severity/status and deterministic decision reason.
- Policy bounds, measured values, duration convention, and supporting reading IDs/timestamps.
- Warning if evidence is incomplete due to a data gap or calibration problem.
- Create and view corrective actions.
- Do not claim product is safe/unsafe for release; leave disposition to an authorized human.

## Accessibility and UX
- Use clear labels and units.
- Do not rely on color alone to convey severity.
- Show timestamps with timezone.
- Display synthetic-data banner in demo mode.
- Show API errors and allow retry.

## Optional AI incident investigation assistant
Purpose: summarize an incident from retrieved evidence and approved procedure text. This is an enhancement, not a dependency for monitoring.

### Input
- `excursion_id`
- retrieved excursion record, policy version, relevant readings, gaps, calibration state, custody timeline, corrective actions
- optionally relevant approved SOP/policy documents

### Output
- concise incident summary;
- evidence-backed facts, each linked to record IDs/timestamps;
- what is unknown or uncertain;
- suggested investigation checklist for human review;
- sources used.

### Guardrails
- The deterministic engine remains the authority for excursion detection, duration, severity, and status.
- Do not pass ground-truth labels to the AI.
- Do not allow the model to create or modify database records directly.
- Do not assert a cause unless evidence supports it.
- If evidence is incomplete, say so explicitly.
- If the LLM provider fails, show the underlying deterministic incident details and a graceful error.
- Log provider/model version and request metadata without logging secrets.
- Test fabricated-ID prompts, insufficient evidence, contradictory records, and provider failures.
- Prefer SQL retrieval for structured telemetry. A vector database is unnecessary unless approved procedure documents need semantic retrieval.
