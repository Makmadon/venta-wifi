import uuid
from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import Event, Ticket, Transaction, TicketStatus, TransactionStatus
from app.schemas import PurchaseRequest, PurchaseResponse, TicketDetailResponse
from app.security import generate_ticket_hash
from app.qr_service import generate_qr_base64_png, generate_qr_png_bytes, generate_qr_svg
from app.config import settings

router = APIRouter(tags=["Tickets"])
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)

def utc_now():
    return datetime.now(timezone.utc)

@router.post("/api/tickets/purchase", response_model=PurchaseResponse)
def purchase_tickets(req: PurchaseRequest, db: Session = Depends(get_db)):
    """
    Guarantees atomic ticket purchase with ZERO race conditions / zero overselling.
    Implements optimistic concurrency and explicit SQLite transaction isolation.
    """
    event = db.query(Event).filter(Event.id == req.event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    purchased_tickets: List[TicketDetailResponse] = []
    total_amount = 0.0

    try:
        # Acquire SQLite write lock immediately (BEGIN IMMEDIATE) to prevent deadlocks
        db.execute(text("BEGIN IMMEDIATE"))

        # Release any expired reservations (older than 10 minutes)
        cutoff_time = utc_now() - timedelta(minutes=10)
        db.execute(
            text("UPDATE tickets SET status = 'AVAILABLE', reserved_at = NULL WHERE status = 'RESERVED' AND reserved_at < :cutoff"),
            {"cutoff": cutoff_time}
        )

        tickets_to_process = []
        if req.ticket_id:
            # Specific seat/ticket requested
            tickets_to_process.append(req.ticket_id)
        else:
            # General admission - select available candidates
            rows = db.execute(
                text("SELECT id FROM tickets WHERE event_id = :event_id AND status = 'AVAILABLE' LIMIT :qty"),
                {"event_id": req.event_id, "qty": req.quantity}
            ).fetchall()
            if len(rows) < req.quantity:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Only {len(rows)} tickets available. Requested {req.quantity}."
                )
            tickets_to_process = [r[0] for r in rows]

        for t_id in tickets_to_process:
            # Cryptographic tamper-proof HMAC hash for this specific ticket and buyer
            qr_hash = generate_ticket_hash(ticket_id=t_id, event_id=event.id, buyer_name=req.buyer_name)

            # Atomic conditional update: ONLY update if currently AVAILABLE
            update_stmt = text("""
                UPDATE tickets
                SET status = 'SOLD',
                    buyer_name = :buyer_name,
                    buyer_contact = :buyer_contact,
                    qr_hash = :qr_hash
                WHERE id = :ticket_id AND status = 'AVAILABLE';
            """)
            result = db.execute(update_stmt, {
                "ticket_id": t_id,
                "buyer_name": req.buyer_name.strip(),
                "buyer_contact": req.buyer_contact.strip(),
                "qr_hash": qr_hash
            })

            # Check if exactly 1 row was updated
            if result.rowcount == 0:
                # Race condition detected: another process claimed this ticket in parallel!
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="One or more selected tickets were just purchased by another customer. Please retry."
                )

            # Record financial transaction
            tx_id = str(uuid.uuid4())
            tx_stmt = text("""
                INSERT INTO transactions (id, ticket_id, amount, status, timestamp)
                VALUES (:id, :ticket_id, :amount, :status, :timestamp);
            """)
            db.execute(tx_stmt, {
                "id": tx_id,
                "ticket_id": t_id,
                "amount": event.price,
                "status": TransactionStatus.COMPLETED,
                "timestamp": utc_now()
            })

            total_amount += event.price

        # Commit atomic batch
        db.commit()

        # Build response with generated QR codes
        for t_id in tickets_to_process:
            t_obj = db.query(Ticket).filter(Ticket.id == t_id).first()
            qr_data = f"{settings.BASE_URL}/api/tickets/verify?code={t_obj.qr_hash}"
            qr_base64 = generate_qr_base64_png(qr_data)
            
            purchased_tickets.append(TicketDetailResponse(
                id=t_obj.id,
                event_id=t_obj.event_id,
                seat_number=t_obj.seat_number,
                status=t_obj.status,
                buyer_name=t_obj.buyer_name,
                buyer_contact=t_obj.buyer_contact,
                qr_hash=t_obj.qr_hash,
                used_at=t_obj.used_at,
                created_at=t_obj.created_at,
                event_title=event.title,
                event_price=event.price,
                qr_base64=qr_base64
            ))

        return PurchaseResponse(
            success=True,
            message="Tickets purchased successfully!",
            tickets=purchased_tickets,
            total_amount=total_amount
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transaction failed: {str(e)}"
        )

@router.get("/api/tickets/{ticket_id}", response_model=TicketDetailResponse)
def get_ticket_api(ticket_id: str, db: Session = Depends(get_db)):
    """
    Get ticket metadata via JSON API.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    
    qr_data = f"{settings.BASE_URL}/api/tickets/verify?code={ticket.qr_hash or ticket.id}"
    qr_b64 = generate_qr_base64_png(qr_data) if ticket.qr_hash else None

    return TicketDetailResponse(
        id=ticket.id,
        event_id=ticket.event_id,
        seat_number=ticket.seat_number,
        status=ticket.status,
        buyer_name=ticket.buyer_name,
        buyer_contact=ticket.buyer_contact,
        qr_hash=ticket.qr_hash,
        used_at=ticket.used_at,
        created_at=ticket.created_at,
        event_title=ticket.event.title if ticket.event else None,
        event_price=ticket.event.price if ticket.event else 0.0,
        qr_base64=qr_b64
    )

@router.get("/ticket/{ticket_id}", response_class=HTMLResponse)
def view_ticket_html(ticket_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Render a clean, responsive, printable digital ticket page.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    qr_data = f"{settings.BASE_URL}/api/tickets/verify?code={ticket.qr_hash or ticket.id}"
    qr_svg = generate_qr_svg(qr_data)
    qr_b64 = generate_qr_base64_png(qr_data)

    return templates.TemplateResponse(
        request=request,
        name="ticket.html",
        context={
            "ticket": ticket,
            "event": ticket.event,
            "qr_svg": qr_svg,
            "qr_b64": qr_b64,
            "settings": settings
        }
    )

@router.get("/ticket/{ticket_id}/qr.png")
def get_ticket_qr_png(ticket_id: str, db: Session = Depends(get_db)):
    """
    Stream QR code as raw PNG image.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket or not ticket.qr_hash:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Valid ticket QR not found")
    
    qr_data = f"{settings.BASE_URL}/api/tickets/verify?code={ticket.qr_hash}"
    png_bytes = generate_qr_png_bytes(qr_data)
    return Response(content=png_bytes, media_type="image/png")

@router.get("/ticket/{ticket_id}/qr.svg")
def get_ticket_qr_svg(ticket_id: str, db: Session = Depends(get_db)):
    """
    Stream QR code as raw SVG file.
    """
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket or not ticket.qr_hash:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Valid ticket QR not found")
    
    qr_data = f"{settings.BASE_URL}/api/tickets/verify?code={ticket.qr_hash}"
    svg_str = generate_qr_svg(qr_data)
    return Response(content=svg_str, media_type="image/svg+xml")
