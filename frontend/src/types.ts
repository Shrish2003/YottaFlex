export type PageResponse<T> = { items: T[]; page: number; page_size: number; total: number };
export type Finding = {
  finding_id: string; finding_type: string; reason: string; shipment_id: string;
  sensor_id?: string; assignment_id?: string; policy_id?: string; reading_ids: string[];
  excursion_id?: string; started_at?: string; ended_at?: string; duration_minutes?: number;
  severity: string; status: string;
};
export type Reading = {
  reading_id: string; sensor_id: string; recorded_at: string; value: number;
  unit: string; quality_status: string; issue_type?: string;
};
export type Sensor = { sensor_id: string; sensor_type: string; calibrated_at: string; calibration_due_at: string; status: string };
export type Container = { container_id: string; container_type: string; status: string; assignment_id: string; assigned_from: string; assigned_to?: string; sensors: Sensor[] };
export type RouteStop = { route_stop_id: string; sequence_number: number; location: string; planned_arrival: string; actual_arrival?: string; actual_departure?: string; status: string };
export type CustodyEvent = { custody_event_id: string; event_time: string; event_type: string; from_party?: string; to_party: string; location: string; evidence_ref?: string };
export type Excursion = { excursion_id: string; assignment_id: string; container_id: string; shipment_id: string; sensor_id: string; policy_id: string; started_at: string; ended_at?: string; duration_minutes?: number; severity: string; status: string; decision_reason: string };
export type Shipment = {
  shipment_id: string; product_id: string; origin: string; destination: string; planned_departure: string;
  planned_delivery: string; actual_departure?: string; actual_delivery?: string; issue_type?: string; status: string;
  detection_findings: Finding[]; containers: Container[]; route_stops: RouteStop[]; custody_events: CustodyEvent[];
  excursions: Excursion[]; telemetry: Reading[]; telemetry_truncated: boolean;
};
export type Policy = { policy_id: string; product_id: string; version: number; min_temp_c: number; max_temp_c: number; max_excursion_minutes: number; min_humidity_pct?: number; max_humidity_pct?: number; effective_from: string; effective_to?: string };
export type Action = { action_id: string; excursion_id: string; assigned_to: string; action_type: string; description: string; created_at: string; completed_at?: string; status: string; outcome?: string };
export type ExcursionDetail = Excursion & { policy: Policy; sensor: Sensor; evidence: Reading[]; evidence_truncated: boolean; evidence_integrity_warnings: string[]; data_gap_warnings: Finding[]; corrective_actions: Action[]; detection_findings: Finding[] };
export type Quality = { from_timestamp?: string; to_timestamp?: string; shipments_total: number; shipments_by_status: Record<string, number>; excursions_by_status: Record<string, number>; excursions_by_severity: Record<string, number>; open_corrective_actions: number; readings_total: number; telemetry_gap_findings: number; invalid_reading_findings: number; calibration_failure_findings: number; validation_status: string; validation_errors: string[]; validation_warnings: string[]; validation_counts: Record<string, number>; evaluation_metrics: Record<string, unknown> };
export type ValidationCheck = { name: string; status: "passed" | "warning" | "failed"; count: number; examples: string[] };
export type Validation = { validation_status: "passed" | "failed"; errors: string[]; warnings: string[]; counts: Record<string, number>; checks: ValidationCheck[] };
export type GenerateRequest = { seed: number; shipment_count: number; container_count: number; sampling_interval_minutes: number; min_trip_days: number; max_trip_days: number; scenario_counts: Record<string, number>; products: { name: string; category: string; min_temp_c: number; max_temp_c: number; max_excursion_minutes: number }[] };
export type Generation = { run_id: string; status: "completed"; generated_at_utc: string; seed: number; counts: Record<string, number>; validation_status: "passed" };
