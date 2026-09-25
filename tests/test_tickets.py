import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models import Event, Ticket, TicketStatus

client = TestClient(app, follow_redirects=False)

def test_events_list():
    """Verify events can be fetched via API."""
    res = client.get("/api/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) > 0
    assert "title" in events[0]
    assert "available_tickets" in events[0]

def test_purchase_and_validation_lifecycle():
    """
    Test complete lifecycle:
    1. Purchase General Admission Ticket
    2. Check QR Code generated and HMAC signed
    3. Verify ticket at gate (SOLD -> USED)
    4. Attempt duplicate check-in (Must reject with ALREADY_USED)
    """
    # 1. Get first event
    events_res = client.get("/api/events")
    event = events_res.json()[0]

    # 2. Purchase ticket
    purchase_payload = {
        "event_id": event["id"],
        "quantity": 1,
        "buyer_name": "Test User Juan",
        "buyer_contact": "juan@example.com",
        "payment_method": "CASH"
    }
    buy_res = client.post("/api/tickets/purchase", json=purchase_payload)
    assert buy_res.status_code == 200
    buy_data = buy_res.json()
    assert buy_data["success"] is True
    assert len(buy_data["tickets"]) == 1

    ticket = buy_data["tickets"][0]
    ticket_id = ticket["id"]
    qr_hash = ticket["qr_hash"]

    assert ticket["status"] == "SOLD"
    assert ticket["buyer_name"] == "Test User Juan"
    assert qr_hash is not None
    assert len(qr_hash) == 64  # SHA256 hex string

    # 3. View ticket HTML page
    page_res = client.get(f"/ticket/{ticket_id}")
    assert page_res.status_code == 200
    assert "Test User Juan" in page_res.text
    assert qr_hash in page_res.text

    # 4. View QR PNG and SVG
    png_res = client.get(f"/ticket/{ticket_id}/qr.png")
    assert png_res.status_code == 200
    assert png_res.headers["content-type"] == "image/png"

    svg_res = client.get(f"/ticket/{ticket_id}/qr.svg")
    assert svg_res.status_code == 200
    assert "svg" in svg_res.headers["content-type"]

    # 5. First Gatekeeper Scan (Verify)
    verify_res1 = client.post("/api/tickets/verify", json={"code": qr_hash})
    assert verify_res1.status_code == 200
    v1_data = verify_res1.json()
    assert v1_data["status"] == "VALID"
    assert v1_data["ticket"]["status"] == "USED"

    # 6. Second Gatekeeper Scan (Duplicate Entry Prevention)
    verify_res2 = client.post("/api/tickets/verify", json={"code": qr_hash})
    assert verify_res2.status_code == 200
    v2_data = verify_res2.json()
    assert v2_data["status"] == "ALREADY_USED"
    assert "ALREADY USED" in v2_data["message"]

def test_verify_invalid_code():
    """Verify that forged/random QR codes are rejected."""
    verify_res = client.post("/api/tickets/verify", json={"code": "fake-forged-qr-hash-12345"})
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "INVALID"

def test_admin_create_event_and_stats():
    """Verify admin can create events and retrieve aggregate stats."""
    payload = {
        "title": "Fiesta de Prueba VIP",
        "description": "Evento de prueba para validación automática",
        "total_capacity": 15,
        "price": 20.0,
        "has_seat_numbers": True,
        "seat_prefix": "VIP"
    }
    create_res = client.post("/api/admin/events", json=payload)
    assert create_res.status_code == 200
    created_ev = create_res.json()
    assert created_ev["total_capacity"] == 15

    # Check stats
    stats_res = client.get("/api/admin/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_events"] >= 1
    assert stats["total_tickets"] >= 15
