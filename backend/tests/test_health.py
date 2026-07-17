"""Health check and root endpoint tests."""


def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "healthy"
    assert "version" in d


def test_root_endpoint(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "SmartBOQ Pro" in r.json()["message"]


def test_swagger_docs_available(client):
    r = client.get("/docs")
    assert r.status_code == 200


def test_openapi_json_available(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    d = r.json()
    assert d["info"]["title"] == "SmartBOQ Pro"
