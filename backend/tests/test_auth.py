"""Authentication API tests."""
import pytest


def test_register_new_user(client):
    response = client.post("/api/v1/auth/register", json={
        "email": "newuser@test.com",
        "full_name": "Test User",
        "password": "Test@1234",
        "role": "estimation_engineer",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert "hashed_password" not in data


def test_register_duplicate_email(client):
    payload = {"email": "dup@test.com", "full_name": "User", "password": "Test@1234", "role": "estimation_engineer"}
    client.post("/api/v1/auth/register", json=payload)
    r2 = client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


def test_register_weak_password(client):
    r = client.post("/api/v1/auth/register", json={
        "email": "weak@test.com", "full_name": "User",
        "password": "short",   # too short, no uppercase, no digit
        "role": "estimation_engineer",
    })
    assert r.status_code == 422


def test_login_success(client, admin_user):
    r = client.post("/api/v1/auth/login", json={
        "email": "test-admin@smartboq.com",
        "password": "Admin@1234",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test-admin@smartboq.com"


def test_login_wrong_password(client, admin_user):
    r = client.post("/api/v1/auth/login", json={
        "email": "test-admin@smartboq.com",
        "password": "WrongPassword@1",
    })
    assert r.status_code == 401


def test_get_me_authenticated(client, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "test-admin@smartboq.com"


def test_get_me_unauthenticated(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_refresh_token(client, admin_user):
    login = client.post("/api/v1/auth/login", json={
        "email": "test-admin@smartboq.com", "password": "Admin@1234"
    })
    refresh_token = login.json()["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_forgot_password_always_200(client):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@test.com"})
    assert r.status_code == 200   # security: never reveal if email exists
