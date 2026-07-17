# SmartBOQ Pro — Software Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User (Browser)                        │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTPS
┌─────────────────────────▼───────────────────────────────────┐
│                    Nginx Reverse Proxy                        │
│        / → Frontend (React)   /api/ → Backend (FastAPI)     │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
┌──────────────▼──────────┐  ┌────────────▼──────────────────┐
│   React Frontend (SPA)  │  │     FastAPI Backend            │
│                         │  │                                │
│  Vite + TypeScript      │  │  11 API Router modules         │
│  Tailwind + ShadCN      │  │  JWT Authentication            │
│  React Query            │  │  RBAC (4 roles)                │
│  Recharts               │  │  Pydantic validation           │
│  13 Page components     │  │  SQLAlchemy ORM                │
└─────────────────────────┘  └────────────┬──────────────────┘
                                          │
               ┌──────────────────────────┼──────────────────┐
               │                          │                  │
┌──────────────▼──────┐  ┌───────────────▼──┐  ┌───────────▼──────┐
│   PostgreSQL 15     │  │  ML Models        │  │  File Storage    │
│                     │  │  (ml_models/)     │  │  (uploads/)      │
│  11 tables          │  │                   │  │                  │
│  UUID PKs           │  │  concrete_crack   │  │  DXF files       │
│  Alembic migrations │  │  surface_crack    │  │  Inspection imgs │
│  pg_trgm index      │  │  road_damage      │  │  Exported PDFs   │
└─────────────────────┘  │  building_safety  │  └──────────────────┘
                         └───────────────────┘
```

## Database Schema (ER Diagram)

```
users (1) ────────── (N) projects
  │                        │
  │                        ├── (N) buildings
  │                             │
  │                             ├── (N) rooms
  │                             └── (N) estimates
  │                        │
  │                        ├── (N) boqs
  │                             └── (N) boq_items ── materials (1)
  │                        │
  │                        └── (N) reports
  │
  ├── (N) audit_logs
  └── (N) inspections ── projects (N)

materials (1) ── (N) material_rate_history
```

## Request Flow — Quantity Estimation

```
User Input (Building Dimensions)
        │
        ▼
POST /api/v1/estimates/run/{building_id}
        │
        ▼
estimation_engine.run_full_estimation(building)
        │
        ├── calc_excavation()       → ExcavationResult
        ├── calc_pcc()              → PCCResult
        ├── calc_rcc_footing()      → RCCResult
        ├── calc_rcc_column()       → RCCResult
        ├── calc_rcc_beam()         → RCCResult
        ├── calc_rcc_slab()         → RCCResult
        ├── calc_brickwork()        → BrickworkResult
        ├── calc_blockwork()        → BrickworkResult
        ├── calc_plaster_external() → PlasterResult
        ├── calc_plaster_internal() → PlasterResult
        ├── calc_flooring()         → FlooringResult
        ├── calc_paint()            → PaintResult
        ├── calc_waterproofing()    → WaterproofingResult
        └── calc_total_steel()      → SteelResult
        │
        ▼
save_estimates() → PostgreSQL (estimates table)
        │
        ▼
Response: {results, summary} → React Frontend
```

## BOQ Generation Flow

```
Saved Estimates (estimates table)
        │
        ▼
POST /api/v1/boq/{id}/auto-generate
        │
        ▼
auto_generate_from_estimates()
  ├── Group by section (A=Earthwork, B=RCC, C=Masonry...)
  ├── Create BOQItem heading rows
  ├── Create BOQItem data rows (qty from estimates, rate=0)
  └── Save to boq_items table
        │
        ▼
Engineer fills in rates (inline table editing)
        │
        ▼
_recalculate_totals()
  subtotal → overhead → profit → contingency → grand_total
        │
        ▼
Export: PDF (ReportLab) | Excel (openpyxl) | CSV
```

## AI Inspection Flow

```
User uploads image
        │
        ▼
POST /api/v1/inspection/{type}
        │
        ▼
ai_inspection.inspect_*()
  ├── Load model (lazy, cached)
  ├── Preprocess image (224×224, normalize)
  ├── Run inference (Keras predict / PyTorch forward)
  ├── Post-process (class probabilities / bounding boxes)
  ├── Map to severity (none/low/moderate/high/critical)
  └── Generate recommendation + cost estimate
        │
        ▼
Save to inspections table
        │
        ▼
Return: {severity, recommendation, repair_cost, probabilities}
```

## Security Architecture

```
Request
  │
  ├── CORS middleware (allowed origins list)
  ├── TrustedHost middleware
  │
  ▼
JWT Bearer token validation
  ├── decode_token() → user_id
  ├── get_current_user() → User ORM
  └── is_active check
  │
  ▼
RBAC Role Check (dependency injection)
  ├── require_admin          → admin only
  ├── require_admin_or_pm    → admin + project_manager
  └── require_estimator      → all 4 roles
  │
  ▼
Business Logic
  │
  ├── SQL Injection: SQLAlchemy ORM parameterised queries
  ├── Password: bcrypt hashing (rounds=12)
  ├── Input: Pydantic strict validation + Zod (frontend)
  └── File upload: extension whitelist + size limit
```

## Deployment Architecture

```
GitHub Push → main branch
        │
        ▼
GitHub Actions CI/CD
  ├── backend-test   (pytest + coverage)
  ├── frontend-build (tsc + vite build)
  ├── docker-build   (GHCR push)
  └── deploy-prod    (SSH + docker compose pull + alembic)
        │
        ▼
Production VPS (Ubuntu 22.04)
  ├── Nginx (SSL termination, reverse proxy)
  ├── Frontend container (nginx:alpine serving /dist)
  ├── Backend container (uvicorn FastAPI)
  ├── PostgreSQL container (persistent volume)
  └── Automated daily DB backup (cron + pg_dump)
```
