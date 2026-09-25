#!/usr/bin/env python3
"""
Seed script to populate initial demo events and tickets.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, Base, SessionLocal
from app.models import Event, Ticket, Transaction, TicketStatus, TransactionStatus
from app.security import generate_ticket_hash
from datetime import datetime, timezone

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if events already exist
        if db.query(Event).count() > 0:
            print("Database already contains events. Skipping seed.")
            return

        print("Seeding demo events and tickets...")

        # 1. Event: General Admission
        event1 = Event(
            title="Festival de Música Local 2026",
            description="Acceso general al festival de bandas locales, área de comida y escenario principal.",
            total_capacity=100,
            price=15.00
        )
        db.add(event1)
        db.flush()

        # Add 100 general admission tickets
        tickets_ev1 = []
        for i in range(1, 101):
            t = Ticket(
                event_id=event1.id,
                seat_number=None,
                status=TicketStatus.AVAILABLE
            )
            tickets_ev1.append(t)
        db.bulk_save_objects(tickets_ev1)

        # 2. Event: Reserved Seating
        event2 = Event(
            title="Conferencia Tech & Ciberseguridad Offline",
            description="Asientos numerados en auditorio principal. Acceso a ponencias técnicas y talleres.",
            total_capacity=30,
            price=25.00
        )
        db.add(event2)
        db.flush()

        tickets_ev2 = []
        for i in range(1, 31):
            t = Ticket(
                event_id=event2.id,
                seat_number=f"A-{i:02d}",
                status=TicketStatus.AVAILABLE
            )
            tickets_ev2.append(t)
        db.bulk_save_objects(tickets_ev2)

        db.commit()

        # Let's also create 1 pre-sold sample ticket for testing verification in event 1
        sample_ticket = db.query(Ticket).filter(Ticket.event_id == event1.id).first()
        if sample_ticket:
            sample_ticket.status = TicketStatus.SOLD
            sample_ticket.buyer_name = "Ana Martínez (Demo)"
            sample_ticket.buyer_contact = "+593 991122334"
            sample_ticket.qr_hash = generate_ticket_hash(sample_ticket.id, event1.id, sample_ticket.buyer_name)

            sample_tx = Transaction(
                ticket_id=sample_ticket.id,
                amount=event1.price,
                status=TransactionStatus.COMPLETED
            )
            db.add(sample_tx)
            db.commit()

            print(f"Sample Sold Ticket created for testing:")
            print(f"  ID: {sample_ticket.id}")
            print(f"  Buyer: {sample_ticket.buyer_name}")
            print(f"  QR Hash: {sample_ticket.qr_hash}")

        print("Database seeded successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    seed()
