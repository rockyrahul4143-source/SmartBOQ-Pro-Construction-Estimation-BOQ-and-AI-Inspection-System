# SmartBOQ Pro — API Reference

Base URL: `http://localhost:8000/api/v1`
Interactive Docs: `http://localhost:8000/docs`

All protected endpoints require: `Authorization: Bearer <access_token>`

---

## Authentication

### POST /auth/register
Register a new user account.
```json
{
  "email": "user@company.com",
  "full_name": "Ali Hassan",
  "password": "Secure@123",
  "role": "estimation_engineer",
  "company": "ABC Construction",
  "designation": "Senior QS"
}
```
**Response 201:** UserOut schema

### POST /auth/login
```json
{ "email": "user@company.com", "password": "Secure@123" }
```
**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": "...", "email": "...", "role": "..." }
}
```

### POST /auth/refresh
```json
{ "refresh_token": "eyJ..." }
```
**Response 200:** `{ "access_token": "eyJ..." }`

### POST /auth/forgot-password
```json
{ "email": "user@company.com" }
```
**Response 200:** Always returns success (security practice)

---

## Projects

### GET /projects/
Query params: `skip`, `limit`, `status`, `building_type`, `search`

### POST /projects/
```json
{
  "project_name": "G+3 Residential Villa",
  "client_name": "Mr. Ahmed Khan",
  "location": "DHA Phase 5, Lahore",
  "building_type": "residential",
  "num_floors": 4,
  "status": "active"
}
```

### GET /projects/stats
Returns count by status + total estimated cost.

### POST /projects/{id}/archive
Marks project as archived.

---

## Buildings

### POST /buildings/
```json
{
  "project_id": "uuid",
  "building_name": "Main Block",
  "num_floors": 4,
  "plot_length": 15.0,
  "plot_width": 12.0,
  "excavation_depth": 1.5,
  "num_footings": 16,
  "num_columns": 16,
  "floor_height": 3.2,
  "total_external_wall_length": 54.0,
  "total_internal_wall_length": 80.0,
  "num_doors": 12,
  "num_windows": 18
}
```

---

## Quantity Estimation

### POST /estimates/run/{building_id}
Runs all 14 calculations and saves to DB.
**Response:** Full estimation result with material totals.

### GET /estimates/summary/{project_id}
Aggregated material quantities across all work types.

### POST /estimates/calculate/excavation
Live calculation without saving:
```json
{ "plot_length": 15.0, "plot_width": 12.0, "depth": 1.5 }
```

---

## Materials

### GET /materials/
Query: `category`, `search`, `active_only`

### PATCH /materials/{id}/rate
```json
{ "new_rate": 1050.0, "notes": "Market price Q2 2024" }
```

### POST /materials/rate-analysis/calculate
```json
{
  "work_description": "1 m³ M20 RCC Slab",
  "unit": "m3",
  "material_name": "Concrete Ingredients",
  "material_quantity": 1.0,
  "material_rate": 18500,
  "labour_quantity": 2.0,
  "labour_rate": 2000,
  "helper_quantity": 2.0,
  "helper_rate": 1000,
  "equipment_rate": 800,
  "overhead_pct": 10,
  "profit_pct": 10,
  "contingency_pct": 5
}
```

---

## BOQ

### POST /boq/
```json
{
  "project_id": "uuid",
  "title": "Bill of Quantities — Rev 1",
  "overhead_pct": 10.0,
  "profit_pct": 10.0,
  "contingency_pct": 5.0
}
```

### POST /boq/{id}/auto-generate
Reads saved estimates and creates sectioned BOQ items automatically.

### PUT /boq/{id}/items/{item_id}
```json
{ "rate": 45000.0 }
```
Amount and totals recalculate automatically.

---

## Reports

### GET /reports/boq/{id}/pdf
Downloads BOQ as PDF. Professional header, color-coded sections, totals.

### GET /reports/boq/{id}/excel
Downloads BOQ as .xlsx with formatted cells.

### GET /reports/quantity/{project_id}/pdf
Downloads Quantity Report as PDF.

---

## DXF Import

### POST /dxf/upload/{project_id}
Form data: `file` (DXF), `units` (mm/cm/m/ft/in), `apply_to_building` (bool)

**Response:**
```json
{
  "extracted": {
    "total_wall_length_m": 134.5,
    "total_floor_area_m2": 280.0,
    "num_doors": 12,
    "num_windows": 18,
    "rooms": [{ "name": "ROOM", "area_m2": 24.5 }]
  },
  "applied_to_building": true,
  "warnings": []
}
```

---

## AI Inspection

### POST /inspection/concrete-crack
Form data: `file` (image), `project_id` (optional)

**Response:**
```json
{
  "inspection_type": "concrete_crack",
  "model_name": "ConcreteNet (ResNet50 + VGG16 Ensemble)",
  "predicted_class": "Crack Detected",
  "confidence": 0.9823,
  "severity": "high",
  "severity_score": 98.2,
  "recommendation": "Immediate structural engineer assessment required.",
  "repair_urgency": "immediate",
  "estimated_repair_cost_min": 80000,
  "estimated_repair_cost_max": 200000,
  "class_probabilities": { "No Crack": 0.0177, "Crack Detected": 0.9823 },
  "inspection_id": "uuid"
}
```

### POST /inspection/road-damage
Returns bounding boxes for each detected defect:
```json
{
  "detections": [
    { "class": "pothole", "confidence": 0.91, "bbox": [120, 45, 380, 290] }
  ],
  "total_defects": 1,
  "worst_defect": "pothole",
  "severity": "high"
}
```

---

## Analytics

### GET /analytics/dashboard
Returns KPIs + recent projects + status/type distribution charts.

### GET /analytics/cost-trends?months=12
Monthly cost totals for trend chart.

### GET /analytics/material-usage
Aggregate material consumption totals + chart data.

### GET /analytics/project-comparison?project_ids=id1,id2,id3
Side-by-side comparison of multiple projects.
