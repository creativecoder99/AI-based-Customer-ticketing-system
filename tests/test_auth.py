import pytest


def test_register_success(client):
    """Test successful user registration."""
    resp = client.post("/register", json={
        "email": "charlie@example.com",
        "password": "strongpassword123"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "charlie@example.com"
    assert "id" in data
    assert "password_hash" not in data  # Ensure hashed password is never returned


def test_register_duplicate_email(client):
    """Test duplicate registration returns 400 Bad Request."""
    email = "duplicate@example.com"
    resp1 = client.post("/register", json={"email": email, "password": "password123"})
    assert resp1.status_code == 201

    resp2 = client.post("/register", json={"email": email, "password": "password123"})
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]


def test_login_success(client):
    """Test login returns signed JWT."""
    email = "david@example.com"
    pwd = "davidpassword123"
    client.post("/register", json={"email": email, "password": pwd})

    resp = client.post("/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client):
    """Test login with wrong password returns 401 Unauthorized."""
    email = "eve@example.com"
    client.post("/register", json={"email": email, "password": "correctpassword123"})

    resp = client.post("/login", json={"email": email, "password": "wrongpassword"})
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]


def test_get_me_authenticated(client, alice_auth):
    """Test /me returns authenticated user details."""
    resp = client.get("/me", headers=alice_auth["headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == alice_auth["email"]
    assert data["id"] == alice_auth["user"]["id"]


def test_get_me_unauthenticated(client):
    """Test /me without token returns 401 Unauthorized."""
    resp = client.get("/me")
    assert resp.status_code == 401
