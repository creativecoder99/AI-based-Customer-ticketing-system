import pytest


def test_health_endpoint(client):
    """Test /health returns healthy status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["rag_chunks_loaded"] > 0


def test_submit_ticket_end_to_end(client, alice_auth):
    """Test submitting ticket generates and persists decision."""
    resp = client.post(
        "/tickets",
        headers=alice_auth["headers"],
        json={"message": "My delivery arrived 3 hours ago with a chipped mug worth ₹450."}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["user_id"] == alice_auth["user"]["id"]
    assert "decision" in data
    assert data["decision"]["action"] == "APPROVE_REFUND"
    assert data["decision"]["confidence"] > 0


def test_list_tickets(client, alice_auth):
    """Test listing tickets for authenticated user."""
    resp = client.get("/tickets", headers=alice_auth["headers"])
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
