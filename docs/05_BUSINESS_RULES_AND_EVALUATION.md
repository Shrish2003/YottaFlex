# Business Rules, Exception Handling, and Evaluation

## Rule 1 — Policy selection
Select the ThresholdPolicy for the shipment's product that is effective at the reading/event time. Never select a policy solely because its numeric thresholds look convenient. Record `policy_id` and version on every excursion decision.

## Rule 2 — Reading quality versus product compliance
Evaluate two separate questions:
1. Is the sensor value physically/technically plausible and trustworthy?
2. Does a valid reading violate the product's policy?
A physically invalid reading should create a data-quality finding and should not automatically be treated as a confirmed product-temperature excursion. Preserve it as evidence.

## Rule 3 — Threshold comparison
Define whether equality to min/max is considered compliant. Recommended default: values below `min_temp_c` or above `max_temp_c` violate policy; exact boundary values are compliant. Make this configurable only if documented and tested.

## Rule 4 — Excursion grouping and duration
Group consecutive valid violating readings into an excursion according to a documented rule. Because readings are discrete, the exact physical start/end is unknown between samples. For the first implementation, document a convention such as:
- start at the timestamp of the first violating reading;
- end at the timestamp of the first subsequent compliant reading;
- duration is end minus start;
- if no recovery reading exists, mark excursion open and do not pretend its duration is final.
Test boundary cases. Do not use ground truth to calculate the duration.
For gaps inside an excursion window, mark evidence as incomplete and avoid assuming the product was safe during the gap.

## Rule 5 — Missing intervals
Create a data-quality issue whenever expected timestamps are missing beyond the defined tolerance. A gap must not be converted to a synthetic normal reading. Distinguish:
- no observation received;
- invalid observation received;
- valid observation outside product policy.

## Rule 6 — Calibration
If calibration is expired or sensor status is faulty/inactive, flag readings as suspect or invalid according to a documented policy. Preserve raw observations. Do not silently discard them.

## Rule 7 — Route and shipment lifecycle
Validate actual departure <= actual delivery when both exist. Validate route-stop order and custody chronology. A deliberately invalid case such as delivery before departure should be retained as a labelled anomaly and flagged, not silently corrected.

## Rule 8 — Severity and action
Severity thresholds must be deterministic and documented. A simple first version may mark an excursion critical when its duration exceeds the product's `max_excursion_minutes`; otherwise it may be warning/review-required. Product-quality disposition remains a human decision.
For confirmed or suspected incidents, create a linked review/corrective action according to configured rules.

## Rule 9 — Traceability
Every excursion should retain shipment, sensor, policy, timestamps, reason, and references to evidence readings. Corrections are additional events or fields with audit history; do not erase the original evidence.

## Evaluation
Keep a labelled test set and ground truth separate from operational inputs. Report:
- TP, FP, FN, TN where the evaluation unit is defined.
- Precision = TP/(TP+FP), when denominator is nonzero.
- Recall = TP/(TP+FN), when denominator is nonzero.
- F1 score, when defined.
- Data-gap detection recall and false-positive count.
- Policy-selection accuracy.
- Duration absolute error versus expected value for cases with a deterministic expected duration.
- PK/FK violations, duplicate count, invalid enum count, and chronology violations.
- Reproducibility result and row counts.

Define the evaluation unit (for example, scenario case or excursion window) before calculating metrics. Do not mix reading-level and incident-level metrics.

## Minimum test scenarios
- Normal readings inside limits.
- Reading exactly at each policy boundary.
- One brief excursion under the duration threshold.
- One prolonged excursion over the duration threshold.
- Excursion recovery.
- Missing interval during otherwise normal conditions.
- Gap during a suspected excursion.
- Invalid physical reading.
- Expired calibration.
- Wrong product policy deliberately supplied.
- Delivery before departure.
- Duplicate reading timestamp.
- Open excursion without recovery.
- Same-seed reproducibility.
