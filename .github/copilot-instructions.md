# YottaFlex Copilot Instructions

## Sources of truth

- Treat the ten original specification documents in [`docs/`](../docs/) as the project requirements.
- Treat the official candidate submission guidance in [`docs/references/`](../docs/references/) as submission and candidate-conduct requirements.
- Treat [`docs/COPILOT_ARCHITECTURE_REVIEW.md`](../docs/COPILOT_ARCHITECTURE_REVIEW.md) as the architecture analysis and decision register.
- Treat [`docs/PROMPT_HISTORY.md`](../docs/PROMPT_HISTORY.md) as the record of verifiable AI prompts and actions.
- Do not describe proposed implementation decisions as official requirements.
- Preserve the ten original project specification documents unchanged unless the user explicitly authorizes a separate documentation task affecting them.

## Workflow and approval gates

- Use the approved modular-monolith architecture.
- Implement one module at a time in the documented dependency order.
- Before starting a module, inspect the relevant requirements and unresolved decisions.
- Stop after completing and validating a module. Report files changed, commands run, actual results, known limitations, and deferred decisions.
- Wait for explicit user approval before implementing the next module.
- Do not implement application code, install packages, initialize Docker, or modify unrelated files when the user requests analysis or documentation-only work.

## Business-rule and configuration discipline

- Keep business rules in domain or service modules, not API routes or UI components.
- Do not hard-code shipment counts, sampling intervals, trip-duration bounds, scenario proportions, physical sensor ranges, threshold policies, calibration rules, or evaluation thresholds.
- Keep environment-specific values and approved business values configurable and validated.
- Do not create fake dashboard metrics, mock production behavior, or hard-coded demonstration results.
- Do not use ground-truth labels as detection inputs or features.
- Keep operational records, validation results, evaluation labels, and ground truth separate.
- Preserve historical readings and events; do not silently overwrite or delete evidence.

## Reliability, integrity, and security

- Use timezone-aware datetimes and consistent UTC serialization.
- Use stable IDs, with entity-specific formats finalized in the domain-model module.
- Enforce primary keys, foreign keys, unique constraints, valid enums, and lifecycle rules.
- Use isolated seeded randomness for reproducible synthetic data.
- Load secrets and credentials from environment variables; never commit secrets.
- Validate all external input and reject invalid configuration clearly.
- Use safe, explicit error handling. Do not suppress exceptions, silently fall back, or return success-shaped results for failures.
- Do not expose credentials, stack traces, arbitrary filesystem paths, or sensitive data through APIs or logs.
- Keep API models separate from persistence models and keep list endpoints bounded.

## Testing and verification

- Add unit, integration, boundary, failure, and regression tests appropriate to the module.
- Test actual required behavior rather than a proxy.
- Run the smallest relevant existing validation command after changes and report its real output.
- Do not mark tests as passing without running them.
- Verify reproducibility, data integrity, lifecycle behavior, and error paths as each dependent module is implemented.
- Record future AI prompts and verifiable actions in `docs/PROMPT_HISTORY.md`; do not fabricate missing history or validation results.

## Current Module 1 boundary

Module 1 may implement only reusable configuration infrastructure, environment loading, UTC/time utilities, logging, explicit error handling, justified generic ID helpers, isolated seeded randomness, and tests for those capabilities.

Module 1 must not implement database models, migrations, ORM/repositories, synthetic-data generation, scenario injection, business rules, excursion detection, ground-truth evaluation, business API endpoints, frontend code, AI integration, or Docker initialization.

Do not finalize business-specific defaults in Module 1. Shipment counts, sampling intervals, trip-duration bounds, scenario proportions, sensor ranges, excursion policies, and entity-specific ID formats belong to their relevant dependent modules and must remain configurable.
