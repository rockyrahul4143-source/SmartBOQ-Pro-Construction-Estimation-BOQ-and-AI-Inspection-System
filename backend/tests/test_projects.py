"""Project management API tests."""
import pytest


PROJECT_PAYLOAD = {
    "project_name": "Test Villa Project",
    "client_name": "Mr. Test Client",
    "location": "DHA Lahore",
    "building_type": "residential",
    "num_floors": 2,
    "status": "draft",
    "country": "Pakistan",
    "currency": "PKR",
}


def test_create_project(client, auth_headers):
    r = client.post("/api/v1/projects/", json=PROJECT_PAYLOAD, headers=auth_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["project_name"] == "Test Villa Project"
    assert data["project_code"].startswith("SBP-")
    return data["id"]


def test_list_projects(client, auth_headers):
    # Create one first
    client.post("/api/v1/projects/", json=PROJECT_PAYLOAD, headers=auth_headers)
    r = client.get("/api/v1/projects/", headers=auth_headers)
    assert r.status_code == 200
    assert "total" in r.json()
    assert "data" in r.json()


def test_get_project(client, auth_headers):
    created = client.post("/api/v1/projects/", json=PROJECT_PAYLOAD, headers=auth_headers)
    pid = created.json()["id"]
    r = client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == pid


def test_update_project(client, auth_headers):
    created = client.post("/api/v1/projects/", json=PROJECT_PAYLOAD, headers=auth_headers)
    pid = created.json()["id"]
    r = client.put(f"/api/v1/projects/{pid}", json={"status": "active"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_archive_project(client, auth_headers):
    created = client.post("/api/v1/projects/", json=PROJECT_PAYLOAD, headers=auth_headers)
    pid = created.json()["id"]
    r = client.post(f"/api/v1/projects/{pid}/archive", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"


def test_project_stats(client, auth_headers):
    r = client.get("/api/v1/projects/stats", headers=auth_headers)
    assert r.status_code == 200
    assert "total_projects" in r.json()


def test_search_projects(client, auth_headers):
    r = client.get("/api/v1/projects/?search=villa", headers=auth_headers)
    assert r.status_code == 200


def test_invalid_floors(client, auth_headers):
    bad = {**PROJECT_PAYLOAD, "num_floors": 0}
    r = client.post("/api/v1/projects/", json=bad, headers=auth_headers)
    assert r.status_code == 422


def test_unauthenticated_access(client):
    r = client.get("/api/v1/projects/")
    assert r.status_code == 401
