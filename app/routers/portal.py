from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models import Plan, Voucher, Session as WifiSession, SessionStatus
from app.schemas import ConnectRequest, ConnectResponse, SessionStatusResponse, PlanResponse
from app.services import session_manager
from app import firewall

router = APIRouter(tags=["Hotspot Portal"])
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)

def get_client_ip(request: Request) -> str:
    # Check X-Forwarded-For if behind reverse proxy/iptables
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
def hotspot_landing_page(request: Request, db: Session = Depends(get_db)):
    """
    Client Captive Portal Landing Page.
    Detects if the user is already authenticated with active time or needs to enter a PIN.
    """
    client_ip = get_client_ip(request)
    session = session_manager.get_active_session(db, client_ip)
    plans = db.query(Plan).filter(Plan.is_active == True).order_by(Plan.price.asc()).all()

    return templates.TemplateResponse(
        request=request,
        name="portal.html",
        context={
            "settings": settings,
            "client_ip": client_ip,
            "session": session,
            "plans": plans,
            "remaining_seconds": session.remaining_seconds() if session else 0
        }
    )

@router.post("/api/connect", response_model=ConnectResponse)
def connect_with_pin(req: ConnectRequest, request: Request, db: Session = Depends(get_db)):
    """
    Authenticates a client device using a purchased voucher PIN.
    Immediately opens internet access in the firewall and starts the countdown.
    """
    client_ip = get_client_ip(request)
    client_mac = firewall.get_arp_mac(client_ip)
    user_agent = request.headers.get("user-agent", "")[:120]

    try:
        active_sess, msg = session_manager.activate_voucher_for_client(
            db=db,
            raw_pin=req.pin,
            client_ip=client_ip,
            client_mac=client_mac,
            device_info=user_agent
        )

        return ConnectResponse(
            success=True,
            message=msg,
            session_id=active_sess.id,
            expires_at=active_sess.expires_at,
            remaining_seconds=active_sess.remaining_seconds(),
            total_minutes=active_sess.total_minutes
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al conectar: {str(e)}")

@router.post("/api/trial", response_model=ConnectResponse)
def start_free_trial(request: Request, db: Session = Depends(get_db)):
    """
    One-time 5-minute free trial per device.
    """
    client_ip = get_client_ip(request)
    client_mac = firewall.get_arp_mac(client_ip)
    user_agent = request.headers.get("user-agent", "")[:120]

    try:
        trial_sess = session_manager.activate_free_trial(
            db=db,
            client_ip=client_ip,
            client_mac=client_mac,
            device_info=user_agent
        )
        return ConnectResponse(
            success=True,
            message=f"¡Prueba gratuita activada! Tienes {settings.FREE_TRIAL_MINUTES} minutos de internet.",
            session_id=trial_sess.id,
            expires_at=trial_sess.expires_at,
            remaining_seconds=trial_sess.remaining_seconds(),
            total_minutes=trial_sess.total_minutes
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/api/status", response_model=SessionStatusResponse)
def get_current_connection_status(request: Request, db: Session = Depends(get_db)):
    """
    Live status poll for client devices.
    Returns whether internet is currently granted and seconds remaining.
    """
    client_ip = get_client_ip(request)
    session = session_manager.get_active_session(db, client_ip)

    if session and session.remaining_seconds() > 0:
        return SessionStatusResponse(
            is_active=True,
            remaining_seconds=session.remaining_seconds(),
            expires_at=session.expires_at,
            started_at=session.started_at,
            total_minutes=session.total_minutes,
            client_ip=client_ip,
            message="Conexión a Internet activa"
        )

    return SessionStatusResponse(
        is_active=False,
        remaining_seconds=0,
        expires_at=None,
        started_at=None,
        total_minutes=0,
        client_ip=client_ip,
        message="Sin conexión activa o tiempo agotado"
    )

@router.get("/api/plans", response_model=List[PlanResponse])
def get_public_plans(db: Session = Depends(get_db)):
    """
    Returns available time plans and pricing.
    """
    return db.query(Plan).filter(Plan.is_active == True).order_by(Plan.price.asc()).all()
