"""BOQ generator API tests."""
import pytest


def _create_project(client, headers):
    r = client.post("/api/v1/projects/", json={
        "project_name": "BOQ Test Project",
        "client_name": "BOQ Client",
        "location": "Karachi",
        "building_type": "commercial",
        "num_floors": 3,
    }, headers=headers)
    return r.json()["id"]


def test_create_boq(client, auth_headers):
    pid = _create_project(client, auth_headers)
    r = client.post("/api/v1/boq/", json={
        "project_id": pid,
        "title": "Main Contract BOQ",
        "overhead_pct": 10.0,
        "profit_pct": 10.0,
        "contingency_pct": 5.0,
    }, headers=auth_headers)
    assert r.status_code == 201
    d = r.json()
    assert d["boq_number"].startswith("BOQ-")
    assert d["status"] == "draft"
    assert d["revision"] == 1
    return d["id"]


def test_list_boqs_for_project(client, auth_headers):
    pid = _create_project(client, auth_headers)
    client.post("/api/v1/boq/", json={"project_id": pid, "title": "BOQ 1"}, headers=auth_headers)
    r = client.get(f"/api/v1/boq/project/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_add_item_to_boq(client, auth_headers):
    pid = _create_project(client, auth_headers)
    boq = client.post("/api/v1/boq/", json={"project_id": pid, "title": "T"}, headers=auth_headers).json()
    r = client.post(f"/api/v1/boq/{boq['id']}/items", json={
        "item_no": "A.1",
        "description": "Earth Excavation",
        "unit": "m3",
        "quantity": 45.5,
        "rate": 800.0,
    }, headers=auth_headers)
    assert r.status_code == 201
    item = r.json()
    assert item["amount"] == round(45.5 * 800.0, 2)


def test_boq_totals_recalculated(client, auth_headers):
    pid = _create_project(client, auth_headers)
    boq = client.post("/api/v1/boq/", json={
        "project_id": pid, "title": "T",
        "overhead_pct": 10.0, "profit_pct": 10.0, "contingency_pct": 5.0,
    }, headers=auth_headers).json()

    client.post(f"/api/v1/boq/{boq['id']}/items", json={
        "item_no": "1", "description": "Work A", "unit": "m3", "quantity": 100.0, "rate": 5000.0,
    }, headers=auth_headers)

    r = client.get(f"/api/v1/boq/{boq['id']}", headers=auth_headers)
    d = r.json()
    assert d["subtotal"] == 500000.0
    assert d["overhead_amount"] == 50000.0
    assert d["profit_amount"] == 50000.0
    assert d["contingency_amount"] == 25000.0
    assert d["grand_total"] == 625000.0


def test_approve_boq(client, auth_headers):
    pid = _create_project(client, auth_headers)
    boq = client.post("/api/v1/boq/", json={"project_id": pid, "title": "T"}, headers=auth_headers).json()
    r = client.post(f"/api/v1/boq/{boq['id']}/approve", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"
