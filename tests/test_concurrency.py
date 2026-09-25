import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models import Event, Ticket, Transaction, TicketStatus

def test_concurrency_zero_overselling_general_admission():
    """
    CRITICAL INVARIANT TEST:
    Verify that when 25 concurrent requests compete for 5 remaining tickets,
    EXACTLY 5 tickets are sold, ZERO overselling occurs, and all remaining
    20 requests fail cleanly with 409 Conflict.
    """
    # 1. Create a special test event with capacity of exactly 5
    db = SessionLocal()
    test_event = Event(
        title="High Concurrency Race Test Event",
        description="Testing atomic transaction locking with SQLite WAL",
        total_capacity=5,
        price=10.0
    )
    db.add(test_event)
    db.commit()
    db.refresh(test_event)

    for i in range(1, 6):
        t = Ticket(
            event_id=test_event.id,
            status=TicketStatus.AVAILABLE
        )
        db.add(t)
    db.commit()
    event_id = test_event.id
    db.close()

    # 2. Fire 25 concurrent purchases simultaneously
    def attempt_purchase(thread_idx: int):
        # Each thread gets its own independent client to simulate real network clients
        thread_client = TestClient(app, follow_redirects=False)
        payload = {
            "event_id": event_id,
            "quantity": 1,
            "buyer_name": f"Concurrent Buyer {thread_idx}",
            "buyer_contact": f"+1234567{thread_idx:02d}",
            "payment_method": "CASH"
        }
        res = thread_client.post("/api/tickets/purchase", json=payload)
        return res.status_code, res.json()

    results = []
    num_workers = 25
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(attempt_purchase, i) for i in range(num_workers)]
        for f in as_completed(futures):
            results.append(f.result())

    success_count = sum(1 for status_code, _ in results if status_code == 200)
    conflict_count = sum(1 for status_code, _ in results if status_code == 409)

    print(f"\nConcurrency Test Results: {success_count} succeeded, {conflict_count} rejected (409)")

    # Assertions
    assert success_count == 5, f"Expected exactly 5 purchases to succeed, got {success_count}"
    assert conflict_count == 20, f"Expected exactly 20 purchases to fail with 409, got {conflict_count}"

    # Verify Database Invariant
    db = SessionLocal()
    sold_count = db.query(Ticket).filter(
        Ticket.event_id == event_id,
        Ticket.status == TicketStatus.SOLD
    ).count()
    avail_count = db.query(Ticket).filter(
        Ticket.event_id == event_id,
        Ticket.status == TicketStatus.AVAILABLE
    ).count()
    tx_count = db.query(Transaction).join(Ticket).filter(
        Ticket.event_id == event_id
    ).count()
    db.close()

    assert sold_count == 5, f"Database shows {sold_count} sold tickets instead of 5"
    assert avail_count == 0, f"Database shows {avail_count} available tickets instead of 0"
    assert tx_count == 5, f"Database recorded {tx_count} financial transactions instead of 5"


def test_concurrency_race_condition_single_seat():
    """
    CRITICAL INVARIANT TEST:
    Verify that when 10 concurrent requests target the EXACT same seat ID,
    EXACTLY 1 request claims the seat and 9 are rejected.
    """
    db = SessionLocal()
    event = Event(
        title="Single Seat Race Test",
        total_capacity=1,
        price=50.0
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    seat_ticket = Ticket(
        event_id=event.id,
        seat_number="VIP-FRONT-01",
        status=TicketStatus.AVAILABLE
    )
    db.add(seat_ticket)
    db.commit()
    db.refresh(seat_ticket)
    ticket_id = seat_ticket.id
    event_id = event.id
    db.close()

    def attempt_seat_purchase(idx: int):
        thread_client = TestClient(app, follow_redirects=False)
        payload = {
            "event_id": event_id,
            "ticket_id": ticket_id,
            "quantity": 1,
            "buyer_name": f"VIP Buyer {idx}",
            "buyer_contact": "vip@vip.com",
            "payment_method": "CASH"
        }
        res = thread_client.post("/api/tickets/purchase", json=payload)
        return res.status_code, res.json()

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_seat_purchase, i) for i in range(10)]
        for f in as_completed(futures):
            results.append(f.result())

    success_count = sum(1 for status_code, _ in results if status_code == 200)
    conflict_count = sum(1 for status_code, _ in results if status_code == 409)

    assert success_count == 1, f"Expected exactly 1 buyer to get the seat, got {success_count}"
    assert conflict_count == 9, f"Expected 9 buyers to be rejected with 409, got {conflict_count}"

    db = SessionLocal()
    final_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    db.close()

    assert final_ticket.status == TicketStatus.SOLD
    assert final_ticket.qr_hash is not None
