from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models import Event, Ticket, TicketStatus
from app.schemas import EventResponse, SeatStatus

router = APIRouter(prefix="/api/events", tags=["Events"])

@router.get("", response_model=List[EventResponse])
def list_events(db: Session = Depends(get_db)):
    """
    List all active events with live ticket counts.
    """
    events = db.query(Event).order_by(Event.id.asc()).all()
    result = []
    for ev in events:
        avail = db.query(func.count(Ticket.id)).filter(
            Ticket.event_id == ev.id,
            Ticket.status == TicketStatus.AVAILABLE
        ).scalar() or 0
        
        sold = db.query(func.count(Ticket.id)).filter(
            Ticket.event_id == ev.id,
            Ticket.status.in_([TicketStatus.SOLD, TicketStatus.USED])
        ).scalar() or 0
        
        ev_data = EventResponse(
            id=ev.id,
            title=ev.title,
            description=ev.description,
            total_capacity=ev.total_capacity,
            price=ev.price,
            created_at=ev.created_at,
            available_tickets=avail,
            sold_tickets=sold
        )
        result.append(ev_data)
    return result

@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information for a specific event.
    """
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    avail = db.query(func.count(Ticket.id)).filter(
        Ticket.event_id == ev.id,
        Ticket.status == TicketStatus.AVAILABLE
    ).scalar() or 0
    
    sold = db.query(func.count(Ticket.id)).filter(
        Ticket.event_id == ev.id,
        Ticket.status.in_([TicketStatus.SOLD, TicketStatus.USED])
    ).scalar() or 0

    return EventResponse(
        id=ev.id,
        title=ev.title,
        description=ev.description,
        total_capacity=ev.total_capacity,
        price=ev.price,
        created_at=ev.created_at,
        available_tickets=avail,
        sold_tickets=sold
    )

@router.get("/{event_id}/seats", response_model=List[SeatStatus])
def get_event_seats(event_id: int, db: Session = Depends(get_db)):
    """
    Get all seats and their current status for the seat-selection view.
    """
    tickets = db.query(Ticket).filter(
        Ticket.event_id == event_id,
        Ticket.seat_number.isnot(None)
    ).order_by(Ticket.seat_number.asc()).all()
    
    return [
        SeatStatus(
            id=t.id,
            seat_number=t.seat_number,
            status=t.status
        )
        for t in tickets
    ]
