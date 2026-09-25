from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models import Event, Ticket, Transaction, TicketStatus, TransactionStatus
from app.schemas import (
    VerifyRequest, VerifyResponse, TicketDetailResponse,
    AdminStatsResponse, EventCreate, EventResponse
)
from app.config import settings
from app.qr_service import generate_qr_base64_png

router = APIRouter(tags=["Admin & Validation"])
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)

def utc_now():
    return datetime.now(timezone.utc)

@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    """
    Render the Administrative & Gatekeeping Dashboard.
    """
    events = db.query(Event).order_by(Event.id.asc()).all()
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "events": events,
            "settings": settings
        }
    )

@router.post("/api/tickets/verify", response_model=VerifyResponse)
@router.post("/api/admin/verify", response_model=VerifyResponse)
def verify_ticket(req: VerifyRequest, db: Session = Depends(get_db)):
    """
    Validates a ticket via QR hash or ticket ID.
    Atomically updates SOLD -> USED to prevent double-entry fraud.
    """
    raw_code = req.code.strip()
    
    # Handle if scanner passed full URL
    if "code=" in raw_code:
        raw_code = raw_code.split("code=")[-1].split("&")[0]

    # Search by qr_hash or ticket UUID
    ticket = db.query(Ticket).filter(
        (Ticket.qr_hash == raw_code) | (Ticket.id == raw_code)
    ).first()

    if not ticket:
        return VerifyResponse(
            status="INVALID",
            message="Invalid QR Code. No matching ticket found in database.",
            ticket=None
        )

    event_title = ticket.event.title if ticket.event else "Unknown Event"
    event_price = ticket.event.price if ticket.event else 0.0
    
    ticket_detail = TicketDetailResponse(
        id=ticket.id,
        event_id=ticket.event_id,
        seat_number=ticket.seat_number,
        status=ticket.status,
        buyer_name=ticket.buyer_name,
        buyer_contact=ticket.buyer_contact,
        qr_hash=ticket.qr_hash,
        used_at=ticket.used_at,
        created_at=ticket.created_at,
        event_title=event_title,
        event_price=event_price
    )

    if ticket.status == TicketStatus.USED:
        used_time_str = ticket.used_at.strftime("%H:%M:%S on %Y-%m-%d") if ticket.used_at else "previously"
        return VerifyResponse(
            status="ALREADY_USED",
            message=f"WARNING: Ticket was ALREADY USED at {used_time_str}! Deny entry.",
            ticket=ticket_detail
        )

    if ticket.status == TicketStatus.AVAILABLE or ticket.status == TicketStatus.RESERVED:
        return VerifyResponse(
            status="INVALID",
            message=f"Ticket is not sold (Current status: {ticket.status}). Deny entry.",
            ticket=ticket_detail
        )

    if ticket.status == TicketStatus.SOLD:
        # Atomic check-in
        ticket.status = TicketStatus.USED
        ticket.used_at = utc_now()
        db.commit()
        db.refresh(ticket)
        ticket_detail.status = ticket.status
        ticket_detail.used_at = ticket.used_at

        return VerifyResponse(
            status="VALID",
            message=f"Ticket Verified! Welcome {ticket.buyer_name or 'Guest'}.",
            ticket=ticket_detail
        )

    return VerifyResponse(
        status="INVALID",
        message="Unknown ticket status.",
        ticket=ticket_detail
    )

@router.get("/api/admin/stats", response_model=AdminStatsResponse)
def get_admin_stats(db: Session = Depends(get_db)):
    """
    Get aggregate sales, check-in metrics, and financial totals.
    """
    total_events = db.query(func.count(Event.id)).scalar() or 0
    total_tickets = db.query(func.count(Ticket.id)).scalar() or 0
    sold_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == TicketStatus.SOLD).scalar() or 0
    used_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == TicketStatus.USED).scalar() or 0
    avail_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status == TicketStatus.AVAILABLE).scalar() or 0

    total_revenue = db.query(func.sum(Transaction.amount)).filter(
        Transaction.status == TransactionStatus.COMPLETED
    ).scalar() or 0.0

    return AdminStatsResponse(
        total_events=total_events,
        total_tickets=total_tickets,
        sold_tickets=sold_tickets,
        used_tickets=used_tickets,
        available_tickets=avail_tickets,
        total_revenue=float(total_revenue)
    )

@router.post("/api/admin/events", response_model=EventResponse)
def create_event(data: EventCreate, db: Session = Depends(get_db)):
    """
    Create a new event and automatically generate ticket inventory.
    Supports either general admission or numbered seat assignment.
    """
    new_event = Event(
        title=data.title,
        description=data.description,
        total_capacity=data.total_capacity,
        price=data.price
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)

    # Populate tickets
    tickets_to_add = []
    for i in range(1, data.total_capacity + 1):
        seat_num = f"{data.seat_prefix}-{i:02d}" if data.has_seat_numbers else None
        t = Ticket(
            event_id=new_event.id,
            seat_number=seat_num,
            status=TicketStatus.AVAILABLE
        )
        tickets_to_add.append(t)

    db.bulk_save_objects(tickets_to_add)
    db.commit()

    return EventResponse(
        id=new_event.id,
        title=new_event.title,
        description=new_event.description,
        total_capacity=new_event.total_capacity,
        price=new_event.price,
        created_at=new_event.created_at,
        available_tickets=data.total_capacity,
        sold_tickets=0
    )

@router.get("/api/admin/tickets")
def list_admin_tickets(
    event_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Search and filter tickets for attendee management and audits.
    """
    q = db.query(Ticket).join(Event)
    if event_id:
        q = q.filter(Ticket.event_id == event_id)
    if status_filter:
        q = q.filter(Ticket.status == status_filter)
    if query:
        search_pattern = f"%{query.strip()}%"
        q = q.filter(
            (Ticket.buyer_name.ilike(search_pattern)) |
            (Ticket.seat_number.ilike(search_pattern)) |
            (Ticket.id.ilike(search_pattern)) |
            (Ticket.buyer_contact.ilike(search_pattern))
        )

    tickets = q.order_by(Ticket.created_at.desc()).limit(limit).all()
    return [
        {
            "id": t.id,
            "event_title": t.event.title,
            "seat_number": t.seat_number or "General",
            "status": t.status,
            "buyer_name": t.buyer_name or "-",
            "buyer_contact": t.buyer_contact or "-",
            "qr_hash": t.qr_hash,
            "used_at": t.used_at.isoformat() if t.used_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in tickets
    ]
