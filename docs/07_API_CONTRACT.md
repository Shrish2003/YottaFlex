# REST API Contract

All JSON timestamps are ISO 8601 UTC. Use Pydantic request/response models. Prefix all routes with `/api`.

## 1. Generate dataset
`POST /api/generate`
Request:
```json
{
  "seed": 20261022,
  "shipment_count": 10,
  "container_count": 5,
  "sampling_interval_minutes": 5,
  "min_trip_days": 2,
  "max_trip_days": 5,
  "scenario_counts": {
    "normal": 10
  },
  "products": [
    {
      "name": "Temperature-sensitive product",
      "category": "cold_chain",
      "min_temp_c": 2,
      "max_temp_c": 8,
      "max_excursion_minutes": 30
    }
  ]
}
```
Response:
```json
{
  "run_id": "GEN-000001",
  "status": "completed",
  "seed": 20261022,
  "counts": {
    "shipments": 10,
    "containers": 5,
    "sensors": 5,
    "sensor_readings": 0
  },
  "validation_status": "passed"
}
```
Counts are illustrative. The implementation must return actual counts. Prevent accidental duplicate generation or provide a documented replace/new-run option.

`scenario_counts` must sum to `shipment_count`, and at least one product specification is
required so that thresholds are never silently invented. `start_datetime`, when supplied,
must be timezone-aware. A generation whose immutable IDs conflict with persisted records
returns `409`; it never replaces existing records.

## 2. List shipments
`GET /api/shipments?status=in_transit&product_id=PRD-000001&origin=Origin&page=1&page_size=25&sort=planned_departure&order=asc`
Response:
```json
{
  "items": [],
  "page": 1,
  "page_size": 25,
  "total": 0
}
```

## 3. Shipment detail
`GET /api/shipments/{shipment_id}`
Return shipment fields and related containers, route stops, custody events, excursions,
bounded telemetry, and detector findings. Telemetry is capped at 500 readings and the
response includes `telemetry_truncated` when the cap is reached. Supported filters are
status, product ID, origin, destination, planned-departure window (`from`/`to`), sort,
and order.

## 4. Shipment summary
`GET /api/shipments/{shipment_id}/summary`
Return counts of readings, gaps, excursions by status/severity, open actions, custody events, and data-quality status. Every count must be derived from persisted data.

## 5. List excursions
`GET /api/excursions?status=open&severity=critical&page=1&page_size=25`
Return paginated excursion records.

## 6. Excursion evidence
`GET /api/excursions/{excursion_id}`
Return:
- excursion details;
- threshold policy bounds and version used;
- relevant sensor and calibration context;
- observed start/end and calculated duration;
- evidence reading IDs, timestamps, values, units, quality statuses, and issue types;
- data-gap warnings;
- related corrective actions;
- deterministic decision reason.

Evidence is bounded to 500 readings and includes `evidence_truncated` when applicable.

## 7. Create corrective action
`POST /api/excursions/{excursion_id}/actions`
Request:
```json
{
  "assigned_to": "quality_engineer",
  "action_type": "review",
  "description": "Review excursion evidence and determine product disposition"
}
```
Response: the persisted action with generated `action_id`, timestamps, and status. Reject unknown excursion IDs.

## 8. Validate
`POST /api/validate`
The current implementation validates the operational records in the configured database.
It does not accept arbitrary server paths or use ground-truth labels as validation input.
Response includes aggregate errors/warnings/counts and `checks`, where each check has
`name`, `status`, `count`, and up to three representative `examples`.

## 9. Quality summary
`GET /api/quality/summary?from=2026-10-01T00:00:00Z&to=2026-11-01T00:00:00Z`
Return aggregate counts and evaluation metrics where available. The evaluation unit is
the generated scenario case, matched by ground-truth shipment ID and the documented
expected-issue-to-detector-finding mapping. Metrics with zero denominators return
`value: null`, `denominator: 0`, and an explicit `unavailable_reason`. Ground truth is
not persisted operationally; after an API restart or an externally loaded dataset,
`evaluation_metrics.available` is false with an explicit unavailable reason.

## 10. Export
`GET /api/exports/{dataset}?format=csv`
Allowed dataset names are an explicit allowlist of persisted operational entities:
`products`, `threshold_policies`, `shipments`, `containers`, `container_assignments`,
`sensors`, `sensor_readings`, `route_stops`, `excursions`, `excursion_evidence`,
`custody_events`, and `corrective_actions`. CSV and JSON are supported. Ground truth is
not exposed by this operational export endpoint because it is a separate generated
artifact and is not persisted in the operational database. Arbitrary paths are rejected.

## Error response
Use a consistent structure:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Shipment not found",
    "details": []
  }
}
```
Suggested status codes: 400 invalid request, 404 unknown ID, 409 conflicting state, 422 schema/validation error, 500 unexpected internal error. Never expose stack traces or credentials.
