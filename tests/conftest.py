import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Create a temporary SQLite database path for isolated test execution
test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db_path = test_db_file.name
test_db_file.close()

# Override DATABASE_PATH before importing app and database modules
os.environ["DATABASE_PATH"] = test_db_path
os.environ["JWT_SECRET"] = "test_secret_key_for_testing_purposes_only"

import src.config
src.config.DATABASE_PATH = test_db_path

from src.database import init_db, get_connection
from src.api import app


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize database tables before any tests run, and clean up after."""
    init_db(test_db_path)
    yield
    try:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
    except Exception:
        pass


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def alice_auth(client):
    """Register and authenticate Alice, returning auth headers and user profile."""
    email = "alice@example.com"
    pwd = "alicepassword123"
    reg_resp = client.post("/register", json={"email": email, "password": pwd})
    if reg_resp.status_code != 201:
        # If already registered in a previous fixture
        pass

    login_resp = client.post("/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_info = client.get("/me", headers=headers).json()
    return {"headers": headers, "user": user_info, "email": email}


@pytest.fixture
def bob_auth(client):
    """Register and authenticate Bob, returning auth headers and user profile."""
    email = "bob@example.com"
    pwd = "bobpassword123"
    reg_resp = client.post("/register", json={"email": email, "password": pwd})
    if reg_resp.status_code != 201:
        pass

    login_resp = client.post("/login", json={"email": email, "password": pwd})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user_info = client.get("/me", headers=headers).json()
    return {"headers": headers, "user": user_info, "email": email}
