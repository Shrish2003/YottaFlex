# Module 4 detection contract

The deterministic detector evaluates operational `GeneratedDataset` records
and returns immutable `DetectionReport` findings. It does not read
`ground_truth` or scenario labels and does not mutate operational records.

- Exact policy boundaries are compliant; values below the minimum or above the
  maximum violate policy.
- A reading is eligible for product-policy evaluation only when its quality is
  valid, its sensor is active and calibrated, and its assignment/container
  attribution is valid.
- Assignment intervals are `[assigned_from, assigned_to)`.
- A missing observation is reported as a telemetry gap when the elapsed time
  exceeds the configured sampling interval. A gap is unknown evidence and
  separates excursion groups.
- Sensor dropout and missing-interval scenarios both appear operationally as
  absent readings; the detector reports the common telemetry-gap finding and
  does not inspect scenario labels to distinguish them.
- An excursion without a recovery observation remains open with no final
  duration.
- The explicitly labelled `duration_undercounted` case remains unresolved for
  independent duration evaluation because the specifications do not define its
  expected duration or boundary expectation.
- The detector reports the explicitly specified delivery-before-departure
  lifecycle anomaly. Other lifecycle rules remain outside this module until
  their semantics are specified.
