# SmartBOQ Pro — Installation Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24+ | Container runtime |
| Docker Compose | 2.20+ | Multi-service orchestration |
| Git | any | Source code |
| Node.js | 20+ | Frontend dev only |
| Python | 3.11+ | Backend dev only |

---

## Quick Start (Docker — Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/smartboq-pro.git
cd smartboq-pro

# 2. Copy environment file and configure
cp .env.example .env
# Edit .env with your settings (especially SECRET_KEY and DB password)

# 3. Start all services
docker compose up -d

# 4. Check services are healthy
docker compose ps

# 5. Open the application
# Frontend:  http://localhost:3000
# API Docs:  http://localhost:8000/docs
# Database:  localhost:5432
```

### Default Credentials (seed data)

| Account | Email | Password | Role |
|---------|-------|----------|------|
| Admin | admin@smartboq.com | Admin@1234 | Administrator |
| Demo | engineer@smartboq.com | Engineer@1234 | Estimation Engineer |

**Change passwords immediately after first login.**

---

## Manual Development Setup

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp ../.env.example .env
# Edit DATABASE_URL to point to your local PostgreSQL

# Run migrations
alembic upgrade head

# Seed data
python -m app.scripts.seed_data

# Start dev server (with hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set environment
echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env.local

# Start dev server
npm run dev
# Opens at http://localhost:5173
```

### PostgreSQL (local)

```bash
# Using Docker for just the database
docker run -d \
  --name smartboq-db \
  -e POSTGRES_DB=smartboq \
  -e POSTGRES_USER=smartboq_user \
  -e POSTGRES_PASSWORD=smartboq_password \
  -p 5432:5432 \
  postgres:15-alpine
```

---

## Environment Variables Reference

```bash
# Application
APP_ENV=development|production
SECRET_KEY=<64-char-random-string>  # CHANGE THIS!
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# CORS (comma-separated origins)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# File uploads
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=50
```

---

## AI Inspection Module Setup

To enable the 4 AI visual inspection models:

```bash
# Install ML dependencies (separate from core requirements)
cd backend
pip install tensorflow==2.16.1
pip install torch==2.3.0 torchvision==0.18.0

# Export trained model weights from Jupyter notebooks
# See: backend/ml_models/README.md for detailed instructions
```

See `backend/ml_models/README.md` for model weight file locations and export commands.

---

## Verify Installation

```bash
# Backend health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "app": "SmartBOQ Pro", "version": "1.0.0"}

# API documentation
open http://localhost:8000/docs
```
