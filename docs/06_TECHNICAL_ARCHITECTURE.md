# Technical Architecture and Implementation Plan

## Architecture
Use a modular monolith for the 72-hour challenge. Avoid microservices.

### Suggested stack
- Backend: Python 3.11+ and FastAPI.
- Validation/models: Pydantic.
- ORM/migrations: SQLAlchemy 2.x and Alembic.
- Database: PostgreSQL; optionally SQLite for fast local tests if compatibility is verified.
- Data processing: standard library first; Pandas may be used for CSV export/analysis where useful.
- Tests: Pytest.
- Frontend: React + TypeScript + Vite, if time allows.
- Local orchestration: Docker Compose.
- API docs: FastAPI OpenAPI/Swagger.
- Optional AI: one LLM-backed evidence explanation endpoint after core functionality is tested.

## Logical components
1. Configuration and seeded random generator.
2. Synthetic master/transaction data generator.
3. Persistence/repository layer.
4. Data-quality validator.
5. Deterministic policy and excursion engine.
6. Event/action service.
7. Evaluation and reporting module.
8. FastAPI routes and Pydantic response models.
9. UI dashboard/detail views.
10. Optional evidence retrieval and AI explanation module.

## Suggested repository layout
```text
yottaflex-cold-chain/
  README.md
  .env.example
  docker-compose.yml
  docs/
    00_README_AND_COPILOT_GUIDE.md
    01_PRD.md
    02_FUNCTIONAL_REQUIREMENTS.md
    03_DATA_MODEL_AND_DICTIONARY.md
    04_SYNTHETIC_DATA_SPEC.md
    05_BUSINESS_RULES_AND_EVALUATION.md
    06_TECHNICAL_ARCHITECTURE.md
    07_API_CONTRACT.md
    08_UI_AND_AI_FEATURE_SPEC.md
    09_TEST_PLAN_AND_DELIVERY.md
  backend/
    app/
      main.py
      core/config.py
      db/
      models/
      schemas/
      repositories/
      services/
        generator.py
        validator.py
        excursion_engine.py
        evaluator.py
        action_service.py
      api/routes/
    tests/
  frontend/
  data/
    generated/
  scripts/
    generate_data.py
    validate_data.py
    evaluate.py
```

## Design rules
- Keep domain rules out of route handlers.
- Keep generation, validation, detection, and evaluation as separate modules.
- Use database transactions for multi-record operations.
- Use parameterized ORM/database operations.
- Add indexes on FK fields, timestamps, status, and shipment identifiers where useful.
- Use migrations for schema changes.
- Keep API models separate from ORM models.
- Return clear validation errors; never expose stack traces or secrets.
- Log scenario IDs and record IDs for debugging, but avoid secrets.
- Do not add distributed queues or vector databases unless a demonstrated need exists.

## Security and reliability
- Store secrets in environment variables.
- Commit `.env.example` only.
- Validate all inputs and dataset scale limits.
- Restrict CORS to the configured frontend origin.
- Avoid accepting arbitrary filesystem paths in export endpoints.
- Add pagination to list endpoints.
- Ensure core monitoring works when the optional LLM provider is unavailable.
- Treat all generated datasets as synthetic and include provenance metadata.

## 72-hour priority
1. Schema, configuration, generator and validation.
2. Deterministic excursion/gap engine and ground-truth evaluation.
3. Persistence and API.
4. Tests, README, reproducibility and exports.
5. Basic UI.
6. Optional AI feature only if core acceptance criteria pass.
