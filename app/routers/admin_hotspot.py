import secrets
import string
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.config import settings
from app.models import Plan, Voucher, Session as WifiSession, Sale, SessionStatus, VoucherStatus
from app.schemas import (
    AdminHotspotStats, AdminSessionItem, VoucherGenerateRequest,
    VoucherBatchResponse, VoucherCard, PlanCreate, PlanResponse
)
from app.services import session_manager
from app.qr_service import generate_qr_base64_png

router = APIRouter(tags=["Admin Hotspot"])
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)

def generate_numeric_pin(length: int = 6) -> str:
    """Generates an easy-to-type, collision-free numeric PIN."""
    return "".join(secrets.choice(string.digits) for _ in range(length))

@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    """
    Renders the Hotspot Business Management Dashboard.
    """
    plans = db.query(Plan).all()
    return templates.TemplateResponse(
        request=request,
        name="admin_hotspot.html",
        context={
            "settings": settings,
            "plans": plans
        }
    )

@router.get("/admin/vouchers/print", response_class=HTMLResponse)
def print_vouchers_sheet(
    plan_id: Optional[int] = None,
    limit: int = 30,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Renders a printable sheet of pocket-sized cut-out voucher cards (fichas).
    Each card has the PIN, duration, price, and QR code for instant login!
    """
    q = db.query(Voucher).filter(Voucher.status == VoucherStatus.AVAILABLE)
    if plan_id:
        q = q.filter(Voucher.plan_id == plan_id)

    vouchers = q.order_by(Voucher.created_at.desc()).limit(limit).all()

    voucher_cards = []
    for v in vouchers:
        login_url = f"{settings.BASE_URL}/?pin={v.pin}"
        qr_b64 = generate_qr_base64_png(login_url)
        voucher_cards.append({
            "pin": v.pin,
            "plan_name": v.plan.name if v.plan else f"{v.duration_minutes}m",
            "duration_minutes": v.duration_minutes,
            "price": v.plan.price if v.plan else 0.0,
            "qr_b64": qr_b64
        })

    return templates.TemplateResponse(
        request=request,
        name="print_vouchers.html",
        context={
            "settings": settings,
            "vouchers": voucher_cards
        }
    )

@router.get("/api/admin/stats", response_model=AdminHotspotStats)
def get_hotspot_stats(db: Session = Depends(get_db)):
    """
    Returns live statistics on active internet users, inventory, and revenue.
    """
    # Check for expired sessions first
    session_manager.check_and_expire_sessions(db)

    active_sess = db.query(func.count(WifiSession.id)).filter(
        WifiSession.status == SessionStatus.ACTIVE
    ).scalar() or 0

    avail_vouchers = db.query(func.count(Voucher.id)).filter(
        Voucher.status == VoucherStatus.AVAILABLE
    ).scalar() or 0

    sold_vouchers = db.query(func.count(Voucher.id)).filter(
        Voucher.status == VoucherStatus.USED
    ).scalar() or 0

    revenue = db.query(func.sum(Sale.amount)).scalar() or 0.0

    return AdminHotspotStats(
        active_sessions=active_sess,
        vouchers_available=avail_vouchers,
        vouchers_sold=sold_vouchers,
        total_revenue=float(revenue)
    )

@router.get("/api/admin/sessions", response_model=List[AdminSessionItem])
def list_active_sessions(db: Session = Depends(get_db)):
    """
    Returns list of devices currently connected to internet.
    """
    session_manager.check_and_expire_sessions(db)

    sessions = db.query(WifiSession).filter(
        WifiSession.status == SessionStatus.ACTIVE
    ).order_by(WifiSession.started_at.desc()).all()

    result = []
    for s in sessions:
        pin = s.voucher.pin if s.voucher else "Prueba Gratis"
        result.append(AdminSessionItem(
            id=s.id,
            client_ip=s.client_ip,
            client_mac=s.client_mac or "Desconocida",
            pin=pin,
            started_at=s.started_at.strftime("%H:%M:%S"),
            expires_at=s.expires_at.strftime("%H:%M:%S"),
            remaining_seconds=s.remaining_seconds(),
            status=s.status,
            device_info=s.device_info
        ))
    return result

@router.post("/api/admin/sessions/{session_id}/extend")
def extend_user_time(session_id: str, minutes: int = 15, db: Session = Depends(get_db)):
    """
    Admin grants extra minutes to a user.
    """
    sess = session_manager.add_time_to_session(db, session_id, minutes)
    if not sess:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")
    return {"success": True, "message": f"Se añadieron {minutes} minutos a {sess.client_ip}"}

@router.post("/api/admin/sessions/{session_id}/revoke")
def disconnect_user_now(session_id: str, db: Session = Depends(get_db)):
    """
    Admin immediately cuts off internet access for a user.
    """
    ok = session_manager.manual_revoke_session(db, session_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada o ya finalizada")
    return {"success": True, "message": "Dispositivo desconectado de internet"}

@router.post("/api/admin/vouchers/generate", response_model=VoucherBatchResponse)
def generate_vouchers_batch(req: VoucherGenerateRequest, db: Session = Depends(get_db)):
    """
    Batch generates unique PIN vouchers for a specific plan.
    """
    plan = db.query(Plan).filter(Plan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    created_cards: List[VoucherCard] = []
    vouchers_to_insert = []

    for _ in range(req.quantity):
        # Generate collision-free PIN
        while True:
            candidate_pin = generate_numeric_pin(6)
            if not db.query(Voucher).filter(Voucher.pin == candidate_pin).first():
                break

        v = Voucher(
            pin=candidate_pin,
            plan_id=plan.id,
            duration_minutes=plan.duration_minutes,
            status=VoucherStatus.AVAILABLE
        )
        vouchers_to_insert.append(v)

        created_cards.append(VoucherCard(
            pin=candidate_pin,
            plan_name=plan.name,
            duration_minutes=plan.duration_minutes,
            price=plan.price,
            qr_data=f"{settings.BASE_URL}/?pin={candidate_pin}"
        ))

    db.bulk_save_objects(vouchers_to_insert)
    db.commit()

    return VoucherBatchResponse(
        total_generated=req.quantity,
        plan_name=plan.name,
        duration_minutes=plan.duration_minutes,
        price=plan.price,
        vouchers=created_cards
    )

@router.get("/api/admin/vouchers")
def list_vouchers(
    status_filter: Optional[str] = None,
    plan_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    q = db.query(Voucher).join(Plan)
    if status_filter:
        q = q.filter(Voucher.status == status_filter)
    if plan_id:
        q = q.filter(Voucher.plan_id == plan_id)

    vouchers = q.order_by(Voucher.created_at.desc()).limit(limit).all()
    return [
        {
            "id": v.id,
            "pin": v.pin,
            "plan_name": v.plan.name if v.plan else "-",
            "duration_minutes": v.duration_minutes,
            "price": v.plan.price if v.plan else 0.0,
            "status": v.status,
            "created_at": v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "-",
            "used_at": v.used_at.strftime("%Y-%m-%d %H:%M") if v.used_at else "-",
            "used_by_ip": v.used_by_ip or "-"
        }
        for v in vouchers
    ]

@router.post("/api/admin/plans", response_model=PlanResponse)
def create_new_plan(data: PlanCreate, db: Session = Depends(get_db)):
    plan = Plan(
        name=data.name,
        duration_minutes=data.duration_minutes,
        price=data.price,
        description=data.description
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan
