import pytest


def test_user_cannot_access_another_users_ticket(client, alice_auth, bob_auth):
    """
    CRITICAL REQUIREMENT (Section 5):
    Demonstrates that a user must only access tickets belonging to their own account.
    Alice's token must not allow Alice to retrieve Bob's ticket (and vice versa).
    """
    # 1. Alice creates a support ticket
    alice_ticket_resp = client.post(
        "/tickets",
        headers=alice_auth["headers"],
        json={"message": "Alice's ticket: My ₹4,500 tea set arrived broken yesterday."}
    )
    assert alice_ticket_resp.status_code == 201
    alice_ticket = alice_ticket_resp.json()
    alice_ticket_id = alice_ticket["id"]

    # 2. Bob creates a support ticket
    bob_ticket_resp = client.post(
        "/tickets",
        headers=bob_auth["headers"],
        json={"message": "Bob's ticket: I want to return my shoes delivered 10 days ago, unused with tags."}
    )
    assert bob_ticket_resp.status_code == 201
    bob_ticket = bob_ticket_resp.json()
    bob_ticket_id = bob_ticket["id"]

    # 3. Alice can retrieve her own ticket
    alice_read_own = client.get(f"/tickets/{alice_ticket_id}", headers=alice_auth["headers"])
    assert alice_read_own.status_code == 200
    assert alice_read_own.json()["id"] == alice_ticket_id
    assert alice_read_own.json()["user_id"] == alice_auth["user"]["id"]

    # 4. Bob can retrieve his own ticket
    bob_read_own = client.get(f"/tickets/{bob_ticket_id}", headers=bob_auth["headers"])
    assert bob_read_own.status_code == 200
    assert bob_read_own.json()["id"] == bob_ticket_id
    assert bob_read_own.json()["user_id"] == bob_auth["user"]["id"]

    # 5. ATTEMPT CROSS-TENANT ACCESS:
    # Alice attempts to access Bob's ticket -> Must be rejected with 403 Forbidden!
    alice_attempts_bob_ticket = client.get(f"/tickets/{bob_ticket_id}", headers=alice_auth["headers"])
    assert alice_attempts_bob_ticket.status_code == 403
    assert "forbidden" in alice_attempts_bob_ticket.json()["detail"].lower()

    # Bob attempts to access Alice's ticket -> Must be rejected with 403 Forbidden!
    bob_attempts_alice_ticket = client.get(f"/tickets/{alice_ticket_id}", headers=bob_auth["headers"])
    assert bob_attempts_alice_ticket.status_code == 403
    assert "forbidden" in bob_attempts_alice_ticket.json()["detail"].lower()


def test_ticket_listing_isolation(client, alice_auth, bob_auth):
    """
    Ensure GET /tickets returns only tickets belonging to the requesting user.
    Alice's ticket list must not include Bob's tickets.
    """
    # Create tickets for Alice and Bob
    client.post("/tickets", headers=alice_auth["headers"], json={"message": "Alice private ticket."})
    client.post("/tickets", headers=bob_auth["headers"], json={"message": "Bob private ticket."})

    # Fetch Alice's tickets
    alice_list = client.get("/tickets", headers=alice_auth["headers"]).json()
    for t in alice_list:
        assert t["user_id"] == alice_auth["user"]["id"]
        assert "Bob" not in t["message"]

    # Fetch Bob's tickets
    bob_list = client.get("/tickets", headers=bob_auth["headers"]).json()
    for t in bob_list:
        assert t["user_id"] == bob_auth["user"]["id"]
        assert "Alice" not in t["message"]


def test_unauthenticated_ticket_access_rejected(client):
    """Ensure accessing tickets without a token returns 401 Unauthorized."""
    resp = client.get("/tickets/1")
    assert resp.status_code == 401
