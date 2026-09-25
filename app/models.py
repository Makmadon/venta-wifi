import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class TicketStatus:
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    USED = "USED"

class TransactionStatus:
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    total_capacity = Column(Integer, nullable=False, default=100)
    price = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    tickets = relationship("Ticket", back_populates="event", cascade="all, delete-orphan")

    def available_count(self) -> int:
        return sum(1 for t in self.tickets if t.status == TicketStatus.AVAILABLE)

    def sold_count(self) -> int:
        return sum(1 for t in self.tickets if t.status in (TicketStatus.SOLD, TicketStatus.USED))

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_number = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default=TicketStatus.AVAILABLE, index=True)
    reserved_at = Column(DateTime, nullable=True)
    buyer_name = Column(String(120), nullable=True)
    buyer_contact = Column(String(120), nullable=True)
    qr_hash = Column(String(64), unique=True, index=True, nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    event = relationship("Event", back_populates="tickets")
    transactions = relationship("Transaction", back_populates="ticket", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ticket_event_status", "event_id", "status"),
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(20), nullable=False, default=TransactionStatus.COMPLETED)
    timestamp = Column(DateTime, default=utc_now, nullable=False)

    ticket = relationship("Ticket", back_populates="transactions")
