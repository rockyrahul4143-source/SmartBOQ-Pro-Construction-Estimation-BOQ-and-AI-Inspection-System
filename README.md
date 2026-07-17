# SmartBOQ Pro — AI-Powered Construction Estimation & Inspection System

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)
![React](https://img.shields.io/badge/React-18-blue?logo=react)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2.21-orange?logo=tensorflow)
![Accuracy](https://img.shields.io/badge/AI%20Accuracy-99.58%25-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

**AI-powered web application for construction estimation, BOQ generation, and structural defect detection**

[Features](#features) • [Demo](#demo) • [Installation](#installation) • [AI Models](#ai-models) • [API Docs](#api-documentation)

</div>

---

## What is SmartBOQ Pro?

SmartBOQ Pro is a full-stack construction management system built for the Indian market. It combines:

- **AI Visual Inspection** — Upload a photo, get instant crack/damage detection with severity scoring
- **Estimation Engine** — Auto-calculate material quantities and costs in INR
- **BOQ Generator** — Generate Bill of Quantities with PDF/Excel export
- **DXF Parser** — Upload AutoCAD drawings to auto-fill dimensions
- **Analytics Dashboard** — Charts, cost trends, project statistics

---

## Features

| Feature | Description |
|---------|-------------|
| 🔍 AI Crack Detection | ResNet50 + VGG16 + InceptionV3 ensemble — **99.58% accuracy** |
| 🚗 Road Damage Detection | MobileNetV2 pothole detection |
| 📊 Estimation Engine | 10+ work types, auto quantity calculation |
| 📋 BOQ Generator | PDF + Excel export with INR rates |
| 🏗️ Project Management | Multi-building, multi-floor projects |
| 📐 DXF AutoCAD Parser | Auto-extract room dimensions |
| 📈 Analytics | Cost trends, severity charts |
| 🔐 JWT Auth | Role-based access (Admin/Engineer/QS/PM) |

---

## AI Models

| Model | File | Accuracy | Size | Purpose |
|-------|------|----------|------|---------|
| ResNet50 | `ResNet50_model.h5` | 99.58% | 93.6 MB | Crack detection |
| VGG16 | `VGG16_model.h5` | 99.5% | 57 MB | Crack detection |
| InceptionV3 | `InceptionV3_model.h5` | 99.4% | 87.1 MB | Crack detection |
| MobileNetV2 | `crack_model.h5` | 99.58% | 20.8 MB | Road damage |

> ⚠️ Model weight files (.h5) are not included in this repo (too large for GitHub).
> Train them yourself using `backend/train_fast.py` with the dataset below.

### Dataset
- **40,000 images** (20,000 crack + 20,000 no-crack)
- Place in `Datasets/Positive/` and `Datasets/Negative/`

---

## Tech Stack

**Backend:** Python 3.12 | FastAPI | SQLAlchemy | SQLite | TensorFlow 2.21 | JWT

**Frontend:** React 18 | TypeScript | Vite | Tailwind CSS | shadcn/ui | Recharts

**AI/ML:** TensorFlow | Keras | Transfer Learning | ResNet50 | VGG16 | InceptionV3 | MobileNetV2

**Reports:** ReportLab (PDF) | OpenPyXL (Excel) | ezdxf (AutoCAD)

---

## Installation

### Requirements
- Python 3.12 (QGIS bundled) or Python 3.11
- Node.js 18+
- Windows 10/11

### Quick Start (Windows)

```bash
# 1. Clone the repo
git clone https://github.com/rockyrahul4143-source/AI-Based-Crack-Detection-in-Concrete-Structures.git
cd AI-Based-Crack-Detection-in-Concrete-Structures

# 2. Double-click start.bat
# OR run manually:

# Backend
cd backend
pip install -r requirements.txt
python setup_local.py
python start_local_py312.py

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Default Login
```
URL:      http://localhost:5173
Email:    admin@smartboq.com
Password: Admin@1234
```

---

## API Documentation

Once running, visit: **http://localhost:8000/docs**

Key endpoints:
```
POST /api/v1/auth/login          — Login
POST /api/v1/auth/register       — Register
POST /api/v1/inspection/concrete-crack   — AI crack detection
POST /api/v1/inspection/road-damage      — Road damage detection
GET  /api/v1/projects/           — List projects
POST /api/v1/boq/generate        — Generate BOQ
GET  /api/v1/analytics/dashboard — Dashboard stats
```

---

## Project Structure

```
smartboq-pro/
├── backend/
│   ├── app/
│   │   ├── api/v1/        ← REST API routes (11 routers)
│   │   ├── models/        ← SQLAlchemy ORM models
│   │   ├── services/      ← AI inference, estimation, reports
│   │   └── core/          ← Auth, config, security
│   ├── ml_models/         ← Trained .h5 model weights (add manually)
│   └── train_fast.py      ← Train all 4 models from dataset
├── frontend/
│   └── src/
│       ├── pages/         ← All UI pages
│       └── components/    ← Reusable components
├── docs/                  ← API reference, architecture docs
├── 1.ipynb                ← Notebook: Ensemble model training
├── 2.ipynb                ← Notebook: MobileNetV2 training
└── start.bat              ← One-click Windows launcher
```

---

## Training the Models

```bash
# Place dataset in:
# Datasets/Positive/  ← 20,000 crack images
# Datasets/Negative/  ← 20,000 no-crack images

cd backend
python train_fast.py
# Trains all 4 models, saves to ml_models/
# Takes ~30-60 minutes on CPU
```

---

## Screenshots

> Dashboard, AI Inspection, BOQ Generator, Estimation Engine

*Coming soon — add screenshots to `/docs/screenshots/`*

---

## License

MIT License — Free to use for education and commercial projects.

---

## Author

**Rocky Rahul** — [GitHub](https://github.com/rockyrahul4143-source)

> Built with ❤️ for the Indian construction industry
