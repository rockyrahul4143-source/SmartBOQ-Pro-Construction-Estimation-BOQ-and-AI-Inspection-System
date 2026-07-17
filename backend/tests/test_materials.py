"""Material database API tests."""
import pytest


MAT = {
    "name": "Test Cement OPC 43",
    "category": "cement",
    "unit": "bag",
    "current_rate": 950.0,
    "supplier_name": "Test Supplier",
}


def test_create_material(client, auth_headers):
    r = client.post("/api/v1/materials/", json=MAT, headers=auth_headers)
    assert r.status_code == 201
    d = r.json()
    assert d["name"] == MAT["name"]
    assert d["current_rate"] == 950.0
    assert d["material_code"].startswith("CEM-")


def test_list_materials(client, auth_headers):
    r = client.get("/api/v1/materials/", headers=auth_headers)
    assert r.status_code == 200
    assert "data" in r.json()


def test_get_material(client, auth_headers):
    created = client.post("/api/v1/materials/", json=MAT, headers=auth_headers)
    mid = created.json()["id"]
    r = client.get(f"/api/v1/materials/{mid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == mid


def test_update_rate(client, auth_headers):
    created = client.post("/api/v1/materials/", json=MAT, headers=auth_headers)
    mid = created.json()["id"]
    r = client.patch(f"/api/v1/materials/{mid}/rate",
                     json={"new_rate": 1050.0, "notes": "Market increase"},
                     headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["current_rate"] == 1050.0


def test_rate_history(client, auth_headers):
    created = client.post("/api/v1/materials/", json=MAT, headers=auth_headers)
    mid = created.json()["id"]
    client.patch(f"/api/v1/materials/{mid}/rate", json={"new_rate": 1000.0}, headers=auth_headers)
    client.patch(f"/api/v1/materials/{mid}/rate", json={"new_rate": 1100.0}, headers=auth_headers)
    r = client.get(f"/api/v1/materials/{mid}/rate-history", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_rate_analysis_endpoint(client, auth_headers):
    r = client.post("/api/v1/materials/rate-analysis/calculate", json={
        "work_description": "1 m³ M20 RCC",
        "unit": "m3",
        "material_name": "Concrete Mix",
        "material_quantity": 8.0,
        "material_rate": 900.0,
        "labour_quantity": 1.5,
        "labour_rate": 1500.0,
        "helper_quantity": 1.0,
        "helper_rate": 800.0,
        "equipment_rate": 500.0,
        "overhead_pct": 10.0,
        "profit_pct": 10.0,
        "contingency_pct": 5.0,
    }, headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["material_cost"] == 8.0 * 900.0
    assert d["total_rate"] > d["direct_cost"]
    assert "breakdown" in d


def test_deactivate_material(client, auth_headers):
    created = client.post("/api/v1/materials/", json=MAT, headers=auth_headers)
    mid = created.json()["id"]
    r = client.delete(f"/api/v1/materials/{mid}", headers=auth_headers)
    assert r.status_code == 200

    # Should not appear in active list
    listed = client.get("/api/v1/materials/?active_only=true", headers=auth_headers)
    ids = [m["id"] for m in listed.json()["data"]]
    assert mid not in ids
