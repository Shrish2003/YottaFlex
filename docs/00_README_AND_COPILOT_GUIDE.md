# YottaFlex Cold-Chain Monitoring Challenge — Documentation Pack

## Purpose
This pack is the source of truth for building the challenge project with Microsoft Copilot. Read the documents in order and implement in small, verifiable increments. Do not generate the entire application in one pass.

## Recommended reading order
1. `01_PRD.md` — product purpose, users, scope, success criteria.
2. `02_FUNCTIONAL_REQUIREMENTS.md` — required behaviors and acceptance criteria.
3. `03_DATA_MODEL_AND_DICTIONARY.md` — entities, fields, relationships, constraints.
4. `04_SYNTHETIC_DATA_SPEC.md` — reproducible synthetic data generation.
5. `05_BUSINESS_RULES_AND_EVALUATION.md` — excursion rules, anomalies, ground truth, metrics.
6. `06_TECHNICAL_ARCHITECTURE.md` — stack, components, repository structure, security.
7. `07_API_CONTRACT.md` — endpoints and request/response shapes.
8. `08_UI_AND_AI_FEATURE_SPEC.md` — dashboard and optional AI investigation assistant.
9. `09_TEST_PLAN_AND_DELIVERY.md` — tests, reproducibility, submission checklist.

## Rules for Copilot
- Treat this documentation pack as requirements. If a requirement is ambiguous, ask a question or document the assumption before coding.
- Implement one milestone at a time. After each milestone, run tests and report files changed, commands run, results, and known issues.
- Do not silently change entity names, ID formats, business rules, or API contracts.
- Prefer simple, maintainable code over unnecessary abstraction or microservices.
- Keep deterministic business logic authoritative. AI may explain evidence, but must not decide whether an excursion occurred.
- Never use ground-truth labels as features or inputs to the detection engine.
- Never fabricate sensor observations or evidence in API responses; all displayed evidence must trace to stored records.
- Use synthetic data only unless lawful external data is explicitly approved and documented.
- Store secrets in environment variables; commit `.env.example`, never real secrets.
- Preserve event history; do not overwrite historical readings, custody events, or corrective-action records.
- If a requirement cannot be completed, explain why and offer the smallest safe alternative.

## Suggested Copilot prompt
"You are helping implement the YottaFlex cold-chain monitoring coding challenge. Read all Markdown files in the `docs/` folder before making changes. Follow the PRD, functional requirements, data model, synthetic-data specification, business rules, API contract, and test plan as the source of truth. Start by inspecting the existing repository and reporting its current state. Then propose a milestone plan; do not rewrite the whole application at once. Implement only Milestone 1 until I approve it. After each milestone, run relevant tests and summarize files changed, commands, results, and unresolved issues."

## Assumptions to confirm
- Initial storage can use PostgreSQL; SQLite may be used for a quick local test mode only if behavior remains compatible.
- The first version assigns each container to one shipment and each sensor to one container. If reassignment/reuse is implemented, assignment history must be retained in an explicit table.
- A temperature excursion is based on product policy and observed readings. The duration convention must be explicit and tested, especially with 5-minute samples and gaps.
- Humidity is collected and displayed, but only evaluated against limits when a product policy explicitly defines humidity limits.
- AI investigation assistant is an enhancement for the AI FDE role, not a replacement for deterministic monitoring.
- Dataset scale is configurable. Begin with a small smoke-test dataset and then run the baseline scale.
