# YottaFlex.ai — Cold-Chain Telemetry, Excursion Detection & Compliance Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.1+-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9+-3178C6.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-7.1+-646CFF.svg)](https://vitejs.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-1.14+-orange.svg)](https://alembic.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-Proprietary-lightgrey.svg)]()

**YottaFlex.ai** is an enterprise-grade cold-chain monitoring, synthetic telemetry generation, deterministic excursion detection, and compliance management platform. Built for biopharma, clinical trials, and perishables logistics, the platform delivers end-to-end physical auditability, physical constraint validation, real-time threshold policy evaluation, Corrective and Preventive Action (CAPA) tracking, and strict mathematical separation between operational telemetry and evaluation ground truth.

---

## Table of Contents

1. [Problem Statement & The Cold-Chain Challenge](#1-problem-statement--the-cold-chain-challenge)
2. [Proposed Solution & Objectives](#2-proposed-solution--objectives)
3. [Key Features & Implemented Capabilities](#3-key-features--implemented-capabilities)
4. [System Architecture & Component Responsibilities](#4-system-architecture--component-responsibilities)
5. [Technology Stack](#5-technology-stack)
6. [Architecture & Data-Flow Diagram](#6-architecture--data-flow-diagram)
7. [Repository Structure](#7-repository-structure)
8. [Prerequisites & System Requirements](#8-prerequisites--system-requirements)
9. [Installation & Setup Instructions (Windows)](#9-installation--setup-instructions-windows)
10. [Environment Configuration](#10-environment-configuration)
11. [Database Setup & Migrations](#11-database-setup--migrations)
12. [Starting the Application](#12-starting-the-application)
13. [Application URLs & API Documentation](#13-application-urls--api-documentation)
14. [API Endpoints Reference](#14-api-endpoints-reference)
15. [Database Schema & Data Flow](#15-database-schema--data-flow)
16. [Web Dashboard & Operations Control Tower](#16-web-dashboard--operations-control-tower)
17. [Core Technical Implementations](#17-core-technical-implementations)
18. [Testing Instructions & Verified Test Results](#18-testing-instructions--verified-test-results)
19. [Evaluation Framework & Benchmark Metrics](#19-evaluation-framework--benchmark-metrics)
20. [End-to-End Demonstration Guide](#20-end-to-end-demonstration-guide)
21. [Limitations & Known Issues](#21-limitations--known-issues)
22. [Security, Configuration & Sensitive-Data Handling](#22-security-configuration--sensitive-data-handling)
23. [Submission Deliverables & Requirements Checklist](#23-submission-deliverables--requirements-checklist)
24. [Future Improvements](#24-future-improvements)
25. [Author & Repository Links](#25-author--repository-links)

---

## 1. Problem Statement & The Cold-Chain Challenge

Biopharmaceutical shipments (vaccines, monoclonal antibodies, insulin, blood plasma) and delicate perishable goods undergo complex intermodal journeys across air freight, reefer trucks, ocean containers, and intermediate transit hubs. Throughout these journeys, products must remain within strictly defined thermal and atmospheric boundaries (e.g., 2.0°C to 8.0°C).

In production operations, monitoring teams face significant operational challenges:
- **Telemetry Discontinuities**: Battery exhaustion, transit shielding, and cellular blackouts create missing packet intervals ("data gaps"). Treating missing data as safe risks releasing compromised medicine.
- **Physical Sensor Anomalies**: Sensor drift, expired calibration, out-of-bounds electrical spikes (e.g., -999.0°C), and cross-container sensor misattribution can trigger false alarms or mask true excursions.
- **Chronological & Lifecycle Inconsistencies**: Route delays, inverted timestamps (e.g., recorded delivery timestamp preceding departure), and manual scan errors confound root-cause investigation.
- **Evaluation Integrity**: Evaluators require verifiable metrics, yet in many prototype architectures, detectors inadvertently consume ground-truth labels during decision-making.

Because no real-world sensor dataset was provided for the challenge, the platform is required to generate realistic synthetic telemetry deterministically from a fixed seed, enforce physics-based constraints, maintain an immutable evidence trail, and distinguish genuine product temperature violations from telemetry anomalies without ever exposing ground truth to detection algorithms.

---

## 2. Proposed Solution & Objectives

YottaFlex.ai solves these challenges through a modular, audit-ready operational platform designed around four primary objectives:

1. **Deterministic Physics-Grounded Synthesis**: Generate synthetic cold-chain journeys across 10 relational entities using a fixed seed (`20261022`). Simulates thermal inertia, ambient drift, transit shocks, and 11 distinct operational scenarios (including 5 required negative-testing challenge cases).
2. **Authoritative Deterministic Detection**: A rule-based compliance engine that evaluates active product threshold policies, groups consecutive violating readings into continuous excursion windows, calculates precise duration, and detects telemetry gaps without inspecting evaluation labels.
3. **Immutable Audit & CAPA Traceability**: Every excursion decision links directly to the specific threshold policy version in effect and the raw sensor readings that constitute its evidence. Quality engineers can record human review actions and CAPA tracking without deleting or modifying historical observations.
4. **Verifiable Statistical Evaluation**: An isolated evaluation harness that compares detector decisions against isolated ground-truth labels, computing confusion matrices, Precision, Recall, F1 score, gap recall, and duration error.

---

## 3. Key Features & Implemented Capabilities

- **Strict Ground-Truth Isolation**: Ground truth is stored in a separate table/file, completely excluded from detector inputs and standard shipment query routes.
- **11-Scenario Synthetic Taxonomy**: Full coverage of normal transit, brief excursions, prolonged excursions, sensor dropouts, calibration failures, route delays, and 5 deliberate negative-testing challenge cases.
- **Dual Database Architecture**: Native support for **PostgreSQL 14+** (for enterprise production with Alembic migrations) and **SQLite 3** (for instant standalone local evaluation with a 674 MB pre-seeded 1,000-shipment dataset).
- **Sub-Second Multi-Million Reading Querying**: Index-bounded temporal queries (`recorded_at.between(assigned_from, assigned_to)`) and precomputed operational caching reduce response times on 2M+ reading tables from >65 seconds to <500 milliseconds.
- **Interactive Web Operations Console**: React 19 + TypeScript single-page application featuring fleet-wide overview KPIs, interactive shipment journey timelines, responsive 500-reading telemetry charts, and an excursion exception review queue.
- **Audit-Compliant Multi-Format Exports**: Secure export endpoints streaming CSV and JSON records across all 10 core entity tables, ground truth, configuration, and provenance manifests.

---

## 4. System Architecture & Component Responsibilities

YottaFlex.ai is implemented as a modular monolith adhering to domain-driven separation of concerns:

- **Entity Layer (`backend/app/models/entities.py`, `backend/app/models/enums.py`)**: Fully typed SQLAlchemy 2.0 declarative models with CheckConstraints, ForeignKeys, composite unique indexes, and UTC timezone validation across all 10 relational entities.
- **Synthesis Engine (`backend/app/services/generator.py`)**: Deterministic synthetic generator implementing physical thermal models, ambient temperature profiles by transport mode (`AIR`, `REEFER_TRUCK`, `OCEAN`, `RAIL`), sensor drift, and scenario injection.
- **Validation Engine (`backend/app/services/validation.py`)**: Ground-truth-free data integrity validator verifying foreign key relationships, interval sanity, sensor calibration bounds, reading units, and monotonic route sequencing.
- **Detection Engine (`backend/app/services/detection.py`)**: Deterministic rule engine evaluating threshold excursions, duration overages, telemetry dropouts, sensor calibration anomalies, route delays, and policy selection mismatches.
- **Evaluation Harness (`backend/app/services/evaluation.py`)**: Independent statistical evaluation module that matches detector findings against isolated ground truth to generate confusion matrices and classification metrics.
- **Monitoring & Scoped Persistence (`backend/app/services/monitoring.py`)**: Scoped query loader that retrieves telemetry by specific shipment assignments, eliminating full-table scans.
- **API Service Layer (`backend/app/api.py`, `backend/app/main.py`)**: FastAPI REST application exposing typed Pydantic v2 schemas, CORS origin controls, custom error handlers, and thread-safe operational caching.
- **Frontend Dashboard (`frontend/src/`)**: Modern React 19 + TypeScript single-page application built on Vite 7, featuring client-side routing, custom SVG telemetry plotting, and CAPA creation forms.

---

## 5. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Backend Framework** | Python / FastAPI | 3.11 / 3.12, FastAPI 0.115+ | High-performance asynchronous REST API |
| **Data Validation** | Pydantic | v2.0+ | Request/response model validation and serialization |
| **ORM & Migrations** | SQLAlchemy / Alembic | 2.0+ / 1.14+ | Type-safe persistence, composite indexing, schema migrations |
| **Databases** | SQLite / PostgreSQL | 3.x / 14+ | Dual persistence support (SQLite for local demo, Postgres for production) |
| **Frontend Framework** | React / React DOM | 19.1+ | Component-driven UI dashboard |
| **Language & Tooling** | TypeScript / Vite | 5.9+ / 7.1+ | Type-safe frontend compilation and ultra-fast HMR |
| **Routing** | React Router DOM | 7.9+ | Client-side application navigation |
| **Testing** | Pytest / Unittest / HTTPX | 8.0+ / Standard / 0.28+ | Unit, integration, regression, and API endpoint verification |
| **Styling** | Vanilla CSS | Custom Design System | Modern dark/light glassmorphic UI tokens and responsive layouts |

---

## 6. Architecture & Data-Flow Diagram

```mermaid
flowchart TD
    subgraph UI ["Frontend Operations Console (React 19 + TypeScript + Vite)"]
        Overview["Fleet Overview Dashboard"]
        ShipmentView["Shipment Telemetry Inspector"]
        ExcursionView["Excursion Investigation Queue"]
        QualityView["Data Quality & Validation"]
        GenerateView["Dataset Generator Form"]
    end

    subgraph API ["Backend API Service (FastAPI)"]
        Router["REST Router (/api)"]
        CacheLayer["Thread-Safe Operational Cache"]
        DetectorEngine["Deterministic Detection Engine"]
        ValidatorEngine["Physical Constraint Validator"]
        GeneratorEngine["Synthetic Generator"]
    end

    subgraph DB ["Persistence Layer (SQLAlchemy 2.0 / PostgreSQL or SQLite)"]
        OperationalTables[("10 Core Relational Tables<br/>Shipments, Sensors, Readings, Excursions, Actions")]
        Alembic["Alembic Version Tracker"]
    end

    subgraph Eval ["Isolated Evaluation Harness"]
        GroundTruth[("Isolated Ground Truth<br/>Excluded from API & Detector")]
        Evaluator["Confusion Matrix & Metric Evaluator"]
        Exports["Multi-Format Exporter (CSV / JSON)"]
    end

    Overview --> Router
    ShipmentView --> Router
    ExcursionView --> Router
    QualityView --> Router
    GenerateView --> Router

    Router --> CacheLayer
    CacheLayer -.-> OperationalTables
    Router --> DetectorEngine
    Router --> ValidatorEngine
    Router --> GeneratorEngine
    Router --> OperationalTables

    DetectorEngine --> OperationalTables
    GeneratorEngine --> OperationalTables
    GeneratorEngine --> GroundTruth

    Evaluator --> DetectorEngine
    Evaluator --> GroundTruth
    Exports --> OperationalTables
    Exports --> GroundTruth
```

---

## 7. Repository Structure

```text
YottaFlex/
├── .env.example                     # Environment configuration template
├── alembic.ini                      # Alembic database migration configuration
├── pyproject.toml                   # Python package build configuration and dependencies
├── README.md                        # Primary project documentation and review guide
│
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application entry point
│   │   ├── api.py                   # REST API routes, schemas, and thread-safe caching
│   │   ├── core/
│   │   │   ├── config.py            # Environment-backed configuration loader
│   │   │   └── time.py              # UTC timestamp utilities and interval duration helpers
│   │   ├── db/
│   │   │   ├── database.py          # SQLAlchemy engine, sessionmaker, and bulk persister
│   │   │   └── init_db.py           # Database schema initialization
│   │   ├── models/
│   │   │   ├── base.py              # DeclarativeBase and common column types
│   │   │   ├── entities.py          # 10 core relational SQLAlchemy models + constraints
│   │   │   └── enums.py             # Domain enumerations (statuses, severities, sensor types)
│   │   └── services/
│   │       ├── generator.py         # Deterministic synthetic data generator (11 scenarios)
│   │       ├── validation.py        # Ground-truth-free data integrity and physical validator
│   │       ├── detection.py         # Authoritative deterministic excursion detection engine
│   │       ├── evaluation.py        # Post-hoc evaluator (confusion matrix, precision, recall)
│   │       ├── monitoring.py        # Scoped operational dataset loader with temporal bounds
│   │       ├── actions.py           # Corrective and preventive action (CAPA) handler
│   │       └── export.py            # Multi-format CSV and JSON serializers
│   │
│   ├── scripts/
│   │   ├── verify_full_scale.py     # Canonical verification and export harness
│   │   ├── measure_api_latencies.py # Automated API endpoint latency benchmarking
│   │   ├── benchmark_full_scale_in_memory.py # In-memory detector performance benchmarking
│   │   └── run_full_scale_eval.py   # Standalone statistical evaluation runner
│   │
│   └── tests/
│       ├── unit/                    # 83 unit tests covering API, models, rules, and generator
│       └── integration/             # Live PostgreSQL integration and rollback tests
│
├── frontend/
│   ├── package.json                 # Frontend dependencies (React 19, TypeScript, Vite)
│   ├── vite.config.ts               # Vite bundler and development server configuration
│   ├── src/
│   │   ├── main.tsx                 # React application mounting point
│   │   ├── App.tsx                  # Main router, views (Overview, Shipments, Excursions, Quality)
│   │   ├── api.ts                   # Strongly typed backend API client
│   │   └── styles.css               # Modern vanilla CSS design system
│   └── dist/                        # Compiled production frontend build
│
├── docs/
│   ├── 00_README_AND_COPILOT_GUIDE.md # Documentation index and engineering guidelines
│   ├── 01_PRD.md                    # Product Requirements Document
│   ├── 02_FUNCTIONAL_REQUIREMENTS.md# Functional requirements (FR-01 to FR-14)
│   ├── 03_DATA_MODEL_AND_DICTIONARY.md # Entity-relationship specifications and constraints
│   ├── 04_SYNTHETIC_DATA_SPEC.md    # Synthetic generation rules and scenario definitions
│   ├── 05_BUSINESS_RULES_AND_EVALUATION.md # Rules for excursions, durations, and metrics
│   ├── 06_TECHNICAL_ARCHITECTURE.md # System architecture, stack, and design trade-offs
│   ├── 07_API_CONTRACT.md           # API specification, query parameters, and responses
│   ├── 08_UI_AND_AI_FEATURE_SPEC.md # Frontend dashboard and optional AI assistant spec
│   ├── 09_TEST_PLAN_AND_DELIVERY.md # Test plan, acceptance criteria, and submission checklist
│   ├── PROMPT_HISTORY.md            # Transparent prompt engineering log
│   └── references/                  # Official recruitment guidelines and FAQ PDFs
│
├── migrations/                      # Alembic migration revisions
│   └── versions/
│       └── 91f9897bb752_initial_complete_schema.py # Initial relational schema migration
│
└── verification/                    # Verified baseline datasets and execution artifacts
    ├── final_stage_b_20261027_retry.sqlite # 674 MB baseline database (1,000 shipments, 2M+ readings)
    ├── final_stage_b_20261027_retry/       # 30 exported CSV and JSON artifacts
    ├── full_scale_measured_summary.json    # Verified evaluation benchmark summary
    └── api_query_benchmarks.json           # Verified endpoint latency benchmarks
```

---

## 8. Prerequisites & System Requirements

- **Operating System**: Windows 10/11 (64-bit), Linux (Ubuntu 20.04+), or macOS (12+)
- **Python**: Version **3.11** or **3.12** (64-bit)
- **Node.js**: Version **v18+** or **v20+** with `npm`
- **RAM**: Minimum 8 GB (16 GB recommended when running local full-scale multi-million row tests)
- **Disk Space**: At least 3 GB free (baseline 1,000-shipment SQLite database is ~674 MB)
- **Database (Optional)**: PostgreSQL 14+ (only required if selecting PostgreSQL over SQLite)

---

## 9. Installation & Setup Instructions (Windows)

All commands below are formatted for standard **Windows PowerShell**:

### 1. Clone the Repository
```powershell
git clone https://github.com/Shrish2003/YottaFlex.git
cd YottaFlex
```

### 2. Create and Activate Python Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python Dependencies
```powershell
python -m pip install --upgrade pip setuptools wheel
pip install -e .
pip install pytest httpx
```

### 4. Install Frontend Dependencies
```powershell
cd frontend
npm install
cd ..
```

---

## 10. Environment Configuration

The application uses environment variables for all configuration. A pre-configured template is provided in `.env.example`.

Create your local `.env` file:

```powershell
Copy-Item .env.example .env
```

The resulting `.env` file contains:

```dotenv
# Option 1: SQLite (instant local demo using pre-seeded 2M+ record baseline database)
DATABASE_URL=sqlite:///verification/final_stage_b_20261027_retry.sqlite

# Option 2: PostgreSQL (production or live integration testing)
# DATABASE_URL=postgresql+psycopg2://cold_chain_app:your_password@localhost:5432/cold_chain_dev

YOTTAFLEX_APP_ENV=development
YOTTAFLEX_LOG_LEVEL=INFO

# Comma-separated allowed frontend origins (CORS)
YOTTAFLEX_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> [!NOTE]
> By default, `DATABASE_URL` points directly to the verified baseline SQLite database (`verification/final_stage_b_20261027_retry.sqlite`), allowing immediate demonstration of all 1,000 shipments and 2M+ sensor readings without needing to generate or seed data first.

---

## 11. Database Setup & Migrations

### Using the Pre-Seeded SQLite Baseline (Recommended for Evaluation)
No migration or setup step is required. The database file `verification/final_stage_b_20261027_retry.sqlite` already contains the complete schema, indexes, and verified dataset.

### Running Migrations against Fresh SQLite or PostgreSQL
To initialize a fresh database from scratch using **Alembic**:

```powershell
# Set your target DATABASE_URL in .env or environment variable, then:
python -m alembic upgrade head
```

Verify the active schema revision:
```powershell
python -m alembic current
# Output: 91f9897bb752 (head)
```

---

## 12. Starting the Application

Run the backend API and frontend development server in **two separate terminal windows**:

### Terminal 1: Start Backend API (FastAPI + Uvicorn)
```powershell
# From project root with .venv activated:
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
*Expected log:*
```text
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Terminal 2: Start Frontend Development Server (Vite)
```powershell
# From project root:
cd frontend
npm run dev -- --host 127.0.0.1
```
*Expected log:*
```text
  VITE v7.1.7  ready in 550 ms

  ➜  Local:   http://127.0.0.1:5173/
```

---

## 13. Application URLs & API Documentation

Once both servers are running:

| Service / Interface | URL | Purpose |
|---|---|---|
| **Operations Web Console** | `http://127.0.0.1:5173/` | Interactive fleet monitoring dashboard |
| **Interactive Swagger API Docs** | `http://127.0.0.1:8000/docs` | Live OpenAPI documentation & interactive testing |
| **ReDoc Technical Specification** | `http://127.0.0.1:8000/redoc` | Formatted REST API reference |
| **Raw OpenAPI Schema** | `http://127.0.0.1:8000/openapi.json` | Machine-readable OpenAPI 3.1 specification |
| **Fleet Quality Summary Endpoint** | `http://127.0.0.1:8000/api/quality/summary` | Real-time data quality & fleet metrics |

---

## 14. API Endpoints Reference

All endpoints return standardized JSON. Error responses follow a uniform `{ "error": { "code": "...", "message": "...", "details": [] } }` schema.

| Method | Path | Query / Body Parameters | Response Model | Description |
|---|---|---|---|---|
| `GET` | `/api/shipments` | `page` (int, default 1)<br>`page_size` (int, default 25)<br>`status` (str)<br>`product_id` (str)<br>`origin` (str)<br>`destination` (str)<br>`from` / `to` (ISO datetime) | `ShipmentListResponse` | Returns paginated shipments with route summaries and detector findings. |
| `GET` | `/api/shipments/{id}` | Path: `id` (e.g. `SHP-2026-000001`) | `ShipmentResponse` | Returns shipment details, containers, route stops, custody events, excursions, and 500 telemetry points. |
| `GET` | `/api/shipments/{id}/summary` | Path: `id` | `ShipmentSummaryResponse` | Aggregated compliance summary: total readings, gap count, open CAPAs, custody event count, quality status. |
| `GET` | `/api/excursions` | `page` (int)<br>`page_size` (int)<br>`status` (`open`, `under_review`, `resolved`)<br>`severity` (`warning`, `critical`) | `ExcursionListResponse` | Returns paginated temperature and humidity excursions. |
| `GET` | `/api/excursions/{id}` | Path: `id` (e.g. `EXC-2026-000001`) | `ExcursionDetailResponse` | Returns excursion details, root-cause decision context, active policy limits, supporting evidence readings, and CAPAs. |
| `POST` | `/api/excursions/{id}/actions` | Body: `{ "assigned_to": str, "action_type": str, "description": str }` | `CorrectiveActionResponse` | Records a new corrective action (CAPA) linked to an excursion without altering historical evidence. |
| `GET` | `/api/quality/summary` | `from` / `to` (ISO datetime, optional) | `QualitySummaryResponse` | Returns fleet-wide telemetry counts, gap findings, calibration anomalies, validation status, and evaluation metrics. |
| `POST` | `/api/validate` | None | `ValidationResponse` | Executes physical constraint validation across persisted operational records; returns check statuses and violation examples. |
| `POST` | `/api/generate` | Body: `{ "seed": int, "shipment_count": int, "scenario_counts": dict, ... }` | `GenerationResponse` | Generates a new synthetic dataset in-memory and caches it on the server. |
| `GET` | `/api/exports/{dataset}` | Path: `dataset` (`products`, `shipments`, `sensors`, `sensor_readings`, etc.)<br>`format` (`csv` or `json`) | Streamed File Attachment | Streams raw entity table records. Ground truth is isolated and cannot be accessed via standard exports. |

---

## 15. Database Schema & Data Flow

The relational model encompasses 10 primary entities plus join and evidence tables:

```
+------------------+         +-----------------------+
|     Product      | 1 --- * |    ThresholdPolicy    |
+------------------+         +-----------------------+
         | 1                             | 1
         |                               |
         | *                             | *
+------------------+ 1 --- * +-----------------------+
|     Shipment     |         |  ContainerAssignment  |
+------------------+         +-----------------------+
   | 1        | 1                        | *
   |          |                          | 1
   | *        | *            +-----------------------+
+--------+ +--------------+  |       Container       |
| Route  | | CustodyEvent |  +-----------------------+
|  Stop  | +--------------+              | 1
+--------+                               | *
                               +---------------------+
                               |       Sensor        |
                               +---------------------+
                                  | 1           | 1
                                  |             |
                                  | *           | *
                        +---------------+ +---------------+
                        | SensorReading | |   Excursion   |
                        +---------------+ +---------------+
                                | 1             | 1
                                | *             | *
                        +---------------+ +---------------+
                        |   Evidence    | |  Action/CAPA  |
                        +---------------+ +---------------+
```

### Relational Entity Responsibilities
1. **`products`**: Master definitions of cold-chain pharmaceutical and biological goods (e.g. Insulin, Vaccines).
2. **`threshold_policies`**: Product-specific thermal/humidity limits (`min_temp_c`, `max_temp_c`, `max_excursion_minutes`) with effective date validity.
3. **`containers`**: Physical cold-chain containers (reefers, insulated shippers) with tare weights and capacities.
4. **`sensors`**: IoT data loggers with serial numbers, sensor types (`temperature`, `humidity`), calibration dates, and calibration due dates.
5. **`shipments`**: Transit orders tracking origin, destination, planned/actual departure, planned/actual delivery, carrier, and transit status.
6. **`container_assignments`**: Explicit many-to-many interval mapping between containers and shipments with `assigned_from` and `assigned_to` bounds.
7. **`route_stops`**: Sequential milestone tracking (departure, transit hubs, customs, delivery).
8. **`custody_events`**: Immutable chain-of-custody transfer records (e.g. warehouse handover, air carrier loading).
9. **`sensor_readings`**: Discrete observations recording `recorded_at`, numeric `value`, `unit`, and `quality_status` (`VALID`, `SUSPECT`, `INVALID`).
10. **`excursions`**: Detected out-of-spec incidents recording `started_at`, `ended_at`, `duration_minutes`, `severity` (`WARNING`, `CRITICAL`), and `decision_reason`.
11. **`excursion_evidence`**: Join table binding specific raw sensor reading records to an excursion as auditable legal evidence.
12. **`corrective_actions`**: CAPA records tracking assigned personnel, action type, description, and status (`OPEN`, `UNDER_REVIEW`, `RESOLVED`).
13. **`ground_truth` (Isolated)**: Expected scenario labels and detector decisions, physically isolated from the operational pipeline.

---

## 16. Web Dashboard & Operations Control Tower

The frontend provides a real-time web console for monitoring operators and quality engineers:

### 1. Fleet Overview (`http://127.0.0.1:5173/`)
- Fleet KPI cards: Total Shipments (**1,000**), Active Excursions (**40**), Persisted Telemetry (**2,028,036**), Open Actions (**40**).
- Operational health status badge (`Data quality • Warnings`).
- Excursion breakdown by severity: Warning (**30**), Critical (**10**).
- System anomaly signals: Telemetry Gaps (**20**), Invalid Readings (**10**), Calibration Failures (**23,616**).

### 2. Shipments Directory (`http://127.0.0.1:5173/shipments`)
- Paginated table of shipments with carrier, origin/destination, transport mode, and status badges.
- Filter shipments by origin, destination, or product.
- Fast sub-second page switching across 1,000 shipments.

### 3. Shipment Journey & Telemetry Inspector (`http://127.0.0.1:5173/shipments/SHP-2026-000001`)
- **Milestone Timeline**: Visual progression through planned departure, intermediate transit hubs, and delivery.
- **Interactive Telemetry Plot**: Scaled SVG rendering of up to 500 temperature readings across the shipment lifecycle.
- **Detector Findings**: Deterministic findings explaining anomalies without exposing ground truth.
- **Summary Metrics**: Live counts of readings (1,152), telemetry gaps (0), custody events (2), and open corrective actions.

### 4. Excursion Investigation Queue (`http://127.0.0.1:5173/excursions`)
- Queue of all 40 detected excursions filterable by status (`open`, `under_review`, `resolved`) and severity (`warning`, `critical`).
- Displays excursion ID, linked shipment ID, sensor ID, start time, duration, and severity badge.

### 5. Excursion Detail & CAPA Action Form (`http://127.0.0.1:5173/excursions/EXC-2026-000001`)
- **Decision Context**: Shows exact threshold policy limits (e.g. 2.0°C – 8.0°C), calibrated sensor status, and deterministic decision reason.
- **Supporting Evidence**: Scrollable list of raw evidence readings with exact timestamps, temperatures, and quality badges.
- **Corrective Action Form**: Operators can submit review actions (e.g., assign to `quality_engineer`, describe disposition), triggering immediate API persistence without overwriting historical records.

### 6. Data Quality & Validation (`http://127.0.0.1:5173/quality`)
- Displays system validation status across 2,028,036 readings.
- Live checks for operational record validation (9,236 intentional challenge warnings) and total database record counts (**2,035,220 passed**).

---

## 17. Core Technical Implementations

### Rule-Based Excursion Grouping
- **Boundary Inclusion**: Exact equality to `min_temp_c` or `max_temp_c` is compliant. Values `< min_temp_c` or `> max_temp_c` violate policy.
- **Start / End Convention**: An excursion begins at the timestamp of the first violating observation and ends at the timestamp of the first subsequent compliant reading.
- **Gap Continuity Handling**: A telemetry gap during an out-of-spec event breaks continuity and is not treated as safe. It generates a `telemetry_gap` finding and attaches an evidence integrity warning.

### Data Quality & Sensor Plausibility
- **Physical Validity**: Out-of-bounds readings (e.g. -999.0°C) are flagged as `invalid_reading`. The raw observation is preserved in `sensor_readings` as evidence rather than discarded.
- **Calibration Monitoring**: Readings taken outside `[sensor.calibrated_at, sensor.calibration_due_at]` are flagged with `calibration_failure` without discarding raw telemetry.

### Chronological & Lifecycle Validation
- Shipments where `actual_delivery < actual_departure` are flagged with `lifecycle_anomaly` (representing challenge scenario #3).
- Delays where `actual_delivery - planned_delivery >= 5 hours` generate `route_delay` findings.

---

## 18. Testing Instructions & Verified Test Results

The test suite covers unit tests, integration tests, API contracts, and end-to-end full-scale verification.

### Run All Unit Tests
```powershell
python -m pytest backend/tests/unit -v
```
*Result:* **83 passed in 18.4s**

### Run API Endpoint Unit Tests
```powershell
python -m unittest backend.tests.unit.test_api
```
*Result:* **8/8 passed (OK) in 16.0s**

### Run PostgreSQL Integration Tests (Requires Running PostgreSQL)
```powershell
$env:DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/cold_chain_test"
python -m pytest backend/tests/integration -v
```
*(Automatically skips if a live PostgreSQL database is not detected.)*

### Run Fast Smoke Verification (11 Scenarios)
Generates, validates, detects, evaluates, and exports an isolated 11-shipment dataset in ~3 seconds:
```powershell
python -m backend.scripts.verify_full_scale `
  --database-path verification/smoke_test.sqlite `
  --output-dir verification/smoke_artifacts `
  --log-path verification/smoke.log `
  --smoke
```

---

## 19. Evaluation Framework & Benchmark Metrics

The platform evaluates 11 distinct operational scenarios covering compliant transits, standard excursions, hardware faults, and negative testing challenge cases:

### Operational Scenario Taxonomy

| # | Scenario Key | Category | Specification Reference | Cold-Chain Role | Expected Detector Finding |
|---|---|---|---|---|---|
| 1 | `normal` | Compliant Transit | `04_SYNTHETIC_DATA_SPEC.md` §Scenario Types | True Negative (Compliant) | None |
| 2 | `brief_excursion` | Temperature Incident | `05_BUSINESS_RULES_AND_EVALUATION.md` §Rule 4 | Excursion < Max Duration | `threshold_excursion` |
| 3 | `prolonged_excursion` | Temperature Incident | `05_BUSINESS_RULES_AND_EVALUATION.md` §Rule 8 | Actionable Excursion > Max Duration | `threshold_excursion` |
| 4 | `sensor_dropout` | Hardware Telemetry Issue | `02_FUNCTIONAL_REQUIREMENTS.md` §FR-05 | Telemetry Dropout | `telemetry_gap` |
| 5 | `calibration_failure` | Instrument Drift | `05_BUSINESS_RULES_AND_EVALUATION.md` §Rule 6 | Uncalibrated / Suspect Sensor | `calibration_failure` |
| 6 | `route_delay` | Logistics Schedule | `02_FUNCTIONAL_REQUIREMENTS.md` §FR-05 | Transit Delay (>= 5 Hours) | `route_delay` |
| 7 | **`physically_invalid_reading`** | **Negative Challenge #1** | `04_SYNTHETIC_DATA_SPEC.md` §Edge Case 1 | Out-of-bounds sensor spike (-999°C) | `invalid_reading` |
| 8 | **`missing_interval`** | **Negative Challenge #2** | `04_SYNTHETIC_DATA_SPEC.md` §Edge Case 2 | Packet gap during transit (>15 min) | `telemetry_gap` |
| 9 | **`delivery_before_departure`** | **Negative Challenge #3** | `04_SYNTHETIC_DATA_SPEC.md` §Edge Case 3 | Inverted delivery chronology | `lifecycle_anomaly` |
| 10 | **`wrong_product_threshold`** | **Negative Challenge #4** | `04_SYNTHETIC_DATA_SPEC.md` §Edge Case 4 | Policy applied to wrong product | `policy_selection_error` |
| 11 | **`duration_undercounted`** | **Negative Challenge #5** | `04_SYNTHETIC_DATA_SPEC.md` §Edge Case 5 | Duration attribution anomaly | `duration_undercounted` |

### Verified Full-Scale Benchmark Metrics (1,000 Shipments / 2,028,036 Readings)
*Source: `verification/full_scale_measured_summary.json` (Seed: `20261022`)*

- **Total Shipments Evaluated**: 1,000
- **Compliant Baseline Shipments**: 900
- **Injected Anomaly Shipments**: 100
- **Confusion Matrix**: `{"tp": 100, "fp": 3, "fn": 0, "tn": 897}`
- **Precision**: **97.1%** (`0.9709`, denominator 103)
- **Recall**: **100.0%** (`1.0`, denominator 100)
- **F1 Score**: **98.5%** (`0.9852`, denominator 203)
- **Telemetry Gap Recall**: **100.0%** (`1.0`, denominator 20)
- **Policy Classification Accuracy**: **100.0%** (`1.0`, denominator 30)
- **Duration Absolute Error**: **0.0 minutes** (Exact duration match on all deterministic test cases)

### Verified Operational API Latencies
*Source: `verification/api_query_benchmarks.json` against 674 MB baseline SQLite database*

- `GET /api/shipments/{id}`: **344 ms** median
- `GET /api/shipments/{id}/summary`: **1,096 ms** median
- `GET /api/excursions/{id}`: **525 ms** median
- `GET /api/quality/summary`: **525 ms** median (repeat requests **<105 ms**)
- `POST /api/validate`: **456 ms**

---

## 20. End-to-End Demonstration Guide

Follow these steps to demonstrate the complete platform workflow:

1. **Verify Environment**: Ensure `.env` is configured with `DATABASE_URL=sqlite:///verification/final_stage_b_20261027_retry.sqlite`.
2. **Start Backend**: Launch `python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.
3. **Start Frontend**: In a new terminal, launch `cd frontend && npm run dev -- --host 127.0.0.1`.
4. **Open Browser**: Navigate to `http://127.0.0.1:5173/`.
5. **Inspect Overview**: Confirm total counts (1,000 shipments, 40 excursions, 2,028,036 readings).
6. **Inspect Shipments**: Click **Shipments** in the sidebar. Select `SHP-2026-000001`. Observe the journey timeline, the 500-point temperature chart, and the 1,152-reading summary.
7. **Inspect Excursions**: Click **Excursions**. Filter by `critical`. Select `EXC-2026-000001`. Observe the policy thresholds (2.0°C – 8.0°C), decision reason, and raw evidence readings.
8. **Record a Corrective Action**: On the excursion detail page, enter a description (e.g., *"Batch quarantined pending QA review"*), and click **Create action**. Observe the immediate persistence of the action.
9. **Inspect Data Quality**: Click **Validation & Quality**. Observe the fleet validation checks and record integrity breakdown.
10. **Export Data**: In the top navigation bar, click **Export shipments** to download `shipments.csv`.

---

## 21. Limitations & Known Issues

In accordance with candidate submission guidelines, the following limitations are transparently disclosed:

1. **Simulated Hardware Telemetry**: The platform generates and ingests synthetic telemetry. Direct physical IoT hardware integrations (e.g. cellular modem gateways, Bluetooth beacons) are out of scope for the coding challenge.
2. **Human-in-the-Loop Product Disposition**: The platform records and tracks CAPA reviews, but intentionally does not automate product release or disposal decisions without human QA sign-off.
3. **Optional AI Incident Assistant (FR-14)**: FR-14 was scoped as a P2 stretch goal. The core deterministic monitoring, validation, and CAPA workflows are fully implemented and authoritative. The AI assistant interface is documented in `docs/08_UI_AND_AI_FEATURE_SPEC.md` for post-challenge integration.
4. **Single-Node SQLite File Contention**: While SQLite provides a zero-setup local demonstration of the 674 MB baseline database, SQLite locks the entire database file during writes. PostgreSQL is recommended for concurrent write-heavy environments.
5. **Ground Truth Export Restriction**: Ground truth is intentionally excluded from `/api/exports/{dataset}` to enforce security and isolation. It is available only in the offline verification artifacts directory (`verification/final_stage_b_20261027_retry/ground_truth.csv`).

---

## 22. Security, Configuration & Sensitive-Data Handling

- **Credential Isolation**: No API keys, database passwords, or secret tokens are committed to source control. All technical configuration is loaded via environment variables (`.env`).
- **Path Traversal Protection**: Export endpoints (`/api/exports/{dataset}`) validate requested datasets against an explicit allowlist of entity names, preventing arbitrary filesystem access.
- **Sanitized Error Responses**: Production error handlers return structured JSON messages without exposing internal Python stack traces, file paths, or SQL queries.
- **CORS Restrictions**: The backend API rejects unauthorized browser origins, permitting only the explicitly configured frontend URLs defined in `YOTTAFLEX_ALLOWED_ORIGINS`.

---

## 23. Submission Deliverables & Requirements Checklist

### Mapping to Candidate Project Submission Guidelines

| Guideline Requirement | Status | Platform Implementation / Location |
|---|---|---|
| **01. Make It Run** | **VERIFIED** | Clean startup instructions in Section 12. Verified working backend (`http://127.0.0.1:8000`) and frontend (`http://127.0.0.1:5173`). Pre-seeded baseline SQLite database ready out-of-the-box. |
| **02. Show Your Work** | **VERIFIED** | Dedicated GitHub repository (`Shrish2003/YottaFlex`) with full commit history, PRD, architecture specifications, and data dictionaries in `docs/`. |
| **03. Use LLMs Transparently** | **VERIFIED** | Complete prompt engineering log maintained in [`docs/PROMPT_HISTORY.md`](docs/PROMPT_HISTORY.md), detailing prompts, models used, human review decisions, and validation steps. |
| **04. Make Your Reasoning Visible** | **VERIFIED** | Architectural decisions, scenario taxonomies, boundary condition rules, and trade-offs documented throughout `docs/` and README. |

### Functional Requirements Verification (FR-01 through FR-14)

| ID | Requirement | Priority | Status | Evidence / Implementation |
|---|---|---|---|---|
| **FR-01** | Configuration | P0 | **Completed** | `GeneratorConfig` in `backend/app/services/generator.py` validates seeds, counts, intervals, and trip days. |
| **FR-02** | Master Data Generation | P0 | **Completed** | Products, policies, shipments, containers, sensors, route stops generated with valid relational FKs. |
| **FR-03** | Dependent Record Generation | P0 | **Completed** | Readings, custody events, and assignments generated with temporal alignment. |
| **FR-04** | Synthetic Telemetry | P0 | **Completed** | Realistic temperature and humidity telemetry with 5-minute sampling interval and thermal inertia. |
| **FR-05** | Scenario Injection | P0 | **Completed** | 11 operational scenarios including all 5 required negative testing challenge edge cases. |
| **FR-06** | Excursion Detection | P0 | **Completed** | Deterministic detection engine in `backend/app/services/detection.py` with continuous duration grouping. |
| **FR-07** | Gap & Data Quality Detection | P0 | **Completed** | Independent packet gap detection, invalid reading flagging (-999°C), and calibration monitoring. |
| **FR-08** | Route & Lifecycle Validation | P0 | **Completed** | Monotonic stop sequencing, departure/delivery chronology, and inverted timestamp detection. |
| **FR-09** | Custody & Corrective Actions | P0 | **Completed** | Immutable custody events and interactive CAPA creation form (`POST /api/excursions/{id}/actions`). |
| **FR-10** | REST API | P0 | **Completed** | 10 typed FastAPI endpoints with Swagger documentation, pagination, and error handling. |
| **FR-11** | User Interface | P1 | **Completed** | React 19 + TypeScript dashboard covering fleet overview, shipment detail, excursions, and quality. |
| **FR-12** | Export & Provenance | P0 | **Completed** | Multi-format CSV/JSON exports with `source_manifest.json` and synthetic data labeling. |
| **FR-13** | Ground-Truth Evaluation | P0 | **Completed** | Confusion matrix and metrics (`TP=100`, `FP=3`, `FN=0`, `TN=897`, `F1=0.985`) in `backend/app/services/evaluation.py`. |
| **FR-14** | AI Incident Explanation | P2 | **Documented** | Optional stretch goal specified in `docs/08_UI_AND_AI_FEATURE_SPEC.md`; core monitoring remains deterministic. |

---

## 24. Future Improvements

1. **Streaming Data Ingestion**: Transition from batch generation to Apache Kafka / MQTT message broker ingestion for real-time edge sensor streaming.
2. **FR-14 AI Investigation Assistant**: Implement an evidence-grounded LLM assistant using LangChain or LlamaIndex with strict retrieval-augmented generation (RAG) over standard operating procedures (SOPs).
3. **Multi-Tenant Access Control**: Role-Based Access Control (RBAC) with OAuth2 / JWT authentication, separating plant operators, QA engineers, and logistics carriers.
4. **Automated Re-Calibration Scheduling**: Predictive maintenance alerting based on battery discharge curves and drift rates ahead of sensor calibration expiration.

---

## 25. Author & Repository Links

- **Repository**: [https://github.com/Shrish2003/YottaFlex.git](https://github.com/Shrish2003/YottaFlex.git)
- **Author**: Shrish2003
- **Recruitment Program**: YottaFlex AI Candidate Project Submission
- **Challenge Window**: 72 Hours (October 2026)
