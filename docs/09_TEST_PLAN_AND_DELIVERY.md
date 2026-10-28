# Test Plan, Evaluation, and Submission Checklist

## Test layers
### Unit tests
- ID generation and parsing.
- Seeded random generator reproducibility.
- Policy selection by product and effective date.
- Threshold boundary behavior.
- Excursion grouping and duration.
- Gap detection.
- Physical validity and calibration checks.
- Lifecycle and custody chronology.
- Evaluation metric calculations.

### Integration tests
- Generate a small dataset and persist it.
- Run validator and excursion engine.
- Verify every FK and related lookup.
- Create a corrective action and confirm original excursion/evidence remains.
- Call API endpoints and validate response schemas.
- Export CSV/JSON and re-import or compare record counts.

### End-to-end acceptance test
1. Start services using documented instructions.
2. Generate a small dataset with fixed seed.
3. Validate all relationships.
4. Run detection.
5. Open a known injected excursion.
6. Confirm the policy, evidence readings, and duration.
7. Confirm a missing interval is flagged.
8. Create a corrective action.
9. Export the records and evaluation report.
10. Run tests and repeat generation with the same seed.

## Reproducibility
- Pin dependency versions where practical.
- Record seed, generator version, configuration, and schema version.
- Normalize timestamps/volatile metadata before checksum comparison.
- Compare logical output checksums across two runs using the same seed/config.
- Report if environment differences affect byte-level reproducibility.

## Evaluation report
Include:
- generation configuration and seed;
- row counts per entity;
- scenario counts;
- PK/FK/enum/temporal validation results;
- excursion TP/FP/FN/TN and precision/recall/F1 if evaluation units support them;
- policy-selection accuracy;
- duration reconciliation errors;
- gap-detection results;
- reproducibility results;
- known limitations.

## Submission checklist
- [ ] Public GitHub repository if required by the challenge.
- [ ] README with setup, configuration, run, test, generation, validation, and export commands.
- [ ] PRD and all docs in `docs/`.
- [ ] Schema/ERD and data dictionary.
- [ ] Synthetic-data generator and fixed seed.
- [ ] Ground truth separate from operational inputs.
- [ ] Business rules and edge cases implemented.
- [ ] Tests and validation report.
- [ ] Sample exports and provenance manifest.
- [ ] `.env.example`; no secrets committed.
- [ ] Screenshots or short demo instructions if useful.
- [ ] Honest list of limitations and unimplemented features.
- [ ] Final deadline and submission method rechecked against the challenge portal.

## Suggested milestones for Copilot
Milestone 1: repository inspection, project skeleton, configuration, models and migrations.
Milestone 2: deterministic synthetic generator for a tiny dataset, then validation.
Milestone 3: scenario injection, separate ground truth, deterministic detection engine.
Milestone 4: evaluation metrics and comprehensive tests.
Milestone 5: persistence and API endpoints.
Milestone 6: exports, README, reproducibility check.
Milestone 7: basic UI.
Milestone 8: optional AI explanation assistant, only if all core acceptance tests pass.
