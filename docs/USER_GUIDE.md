# SmartBOQ Pro — User Guide

## Getting Started

### Step 1 — Login
Navigate to `http://localhost:3000`. Login with your credentials.
Default admin: `admin@smartboq.com` / `Admin@1234`.

### Step 2 — Create a Project
1. Click **Projects** in the sidebar
2. Click **New Project**
3. Fill in: Project Name, Client Name, Location, Building Type, No. of Floors
4. Click **Create Project**

### Step 3 — Add Building Dimensions
1. Click **Buildings** in the sidebar
2. Select your project
3. Click **New Building**
4. Fill in all structural dimensions:
   - Plot dimensions (length × width)
   - Foundation details (footings, PCC)
   - Column and beam dimensions
   - Wall lengths (external + internal)
   - Slab thickness
   - Openings (doors + windows)
   - Steel percentages
5. Click **Save Building**

### Step 4 — Run Quantity Estimation
1. Click **Estimation** in the sidebar
2. Select your project and building
3. Click **Run Estimation**
4. View material summary:
   - Cement bags, Sand (CFT), Aggregate (CFT)
   - Steel (kg/tons), Bricks, Paint, Tiles
5. Download PDF report if needed

### Step 5 — Generate BOQ
1. Click **BOQ** in the sidebar
2. Select project → Click **New BOQ**
3. Click **Auto-Generate** to populate items from estimates
4. Fill in rates for each line item by clicking the pencil icon
5. BOQ totals (overhead + profit + contingency) calculate automatically
6. Click **Approve** when finalized
7. Export as PDF, Excel, or CSV

---

## DXF Import Workflow

If you have AutoCAD drawings:

1. Click **DXF Import**
2. Select your project
3. Choose drawing units (default: mm)
4. Upload your `.dxf` file
5. Review extracted dimensions:
   - Total wall lengths
   - Floor area
   - Door/window counts
6. Toggle **Extract & Apply** to auto-fill the building dimensions
7. Run estimation as normal

### DXF Layer Naming Requirements
Your DXF must use these layer names:

| Element | Layer Names |
|---------|-------------|
| External/Internal Walls | `WALL`, `WALLS`, `EXT_WALL`, `INT_WALL` |
| Doors | `DOOR`, `DOORS` |
| Windows | `WINDOW`, `WINDOWS` |
| Room boundaries | `ROOM`, `FLOOR`, `AREA` |

---

## AI Visual Inspection

1. Click **AI Inspection** in the sidebar
2. Select inspection type:
   - **Concrete Crack** — upload concrete surface photo
   - **Surface Crack Ensemble** — highest accuracy, same image type
   - **Road Damage** — upload road/pavement photo
   - **Building Safety** — upload building exterior/interior photo
3. Optionally link to a project
4. Upload image (drag & drop or click)
5. Click **Run Inspection**
6. View results:
   - Severity: None / Low / Moderate / High / Critical
   - Confidence percentage
   - Specific recommendation
   - Estimated repair cost range (PKR)
7. View inspection history in the **History** tab

---

## Materials & Rate Management

### Update Material Rate (Admin only)
1. Click **Materials** in sidebar
2. Find the material
3. Click the **TrendingUp** icon (📈)
4. Enter new rate and notes
5. Click **Update Rate**

Rate history is automatically recorded for audit purposes.

### Rate Analysis Calculator
Use the Rate Analysis endpoint (`POST /api/v1/materials/rate-analysis/calculate`)
to compute the all-in rate for any unit of work, including:
- Material cost
- Skilled labour cost
- Helper labour cost
- Equipment cost
- Overhead (10%)
- Profit (10%)
- Contingency (5%)

---

## User Roles

| Role | Can Do |
|------|--------|
| **Admin** | Everything — user management, material rates, all projects |
| **Project Manager** | All projects, approve BOQs, view all data |
| **Estimation Engineer** | Own projects, run estimations, create BOQs |
| **Quantity Surveyor** | Own projects, run estimations, create BOQs |
