from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models import Plan, Voucher, Session as WifiSession, Sale, TrialRecord, SessionStatus, VoucherStatus
from app import firewall
from app.config import settings

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def normalize_pin(pin: str) -> str:
    return pin.strip().replace(" ", "").replace("-", "").upper()

def activate_voucher_for_client(
    db: Session,
    raw_pin: str,
    client_ip: str,
    client_mac: Optional[str] = None,
    device_info: Optional[str] = None
) -> Tuple[WifiSession, str]:
    """
    Validates a voucher PIN and grants internet access to the client.
    If the client already has an active session, it tops up (extends) the time!
    """
    pin = normalize_pin(raw_pin)

    # 1. Acquire immediate lock to avoid race conditions
    db.execute(text("BEGIN IMMEDIATE"))

    voucher = db.query(Voucher).filter(Voucher.pin == pin).first()
    if not voucher:
        db.rollback()
        raise ValueError("El código PIN ingresado no existe. Verifica tu ficha.")

    if voucher.status == VoucherStatus.USED:
        db.rollback()
        raise ValueError(f"Esta ficha PIN ya fue utilizada el {voucher.used_at.strftime('%d/%m/%Y %H:%M') if voucher.used_at else ''}.")

    if voucher.status == VoucherStatus.EXPIRED:
        db.rollback()
        raise ValueError("Esta ficha ha expirado.")

    now = utc_now()
    plan_name = voucher.plan.name if voucher.plan else f"{voucher.duration_minutes} Minutos"
    plan_price = voucher.plan.price if voucher.plan else 0.0

    # 2. Check if this IP/MAC already has an active session (Recharge / Top-Up)
    existing_session = db.query(WifiSession).filter(
        WifiSession.client_ip == client_ip,
        WifiSession.status == SessionStatus.ACTIVE,
        WifiSession.expires_at > now
    ).first()

    if existing_session:
        # Extend active session
        existing_session.expires_at = existing_session.expires_at + timedelta(minutes=voucher.duration_minutes)
        existing_session.total_minutes += voucher.duration_minutes
        active_session = existing_session
        action_msg = f"¡Tiempo recargado! Se añadieron {voucher.duration_minutes} minutos a tu conexión."
    else:
        # Create brand new session
        new_session = WifiSession(
            voucher_id=voucher.id,
            client_ip=client_ip,
            client_mac=client_mac,
            device_info=device_info,
            started_at=now,
            expires_at=now + timedelta(minutes=voucher.duration_minutes),
            total_minutes=voucher.duration_minutes,
            status=SessionStatus.ACTIVE
        )
        db.add(new_session)
        db.flush()
        active_session = new_session
        action_msg = f"¡Acceso a Internet Concedido! Tienes {voucher.duration_minutes} minutos disponibles."

    # 3. Mark voucher as used
    voucher.status = VoucherStatus.USED
    voucher.used_at = now
    voucher.used_by_ip = client_ip
    voucher.used_by_mac = client_mac

    # 4. Record sale
    sale = Sale(
        voucher_id=voucher.id,
        plan_name=plan_name,
        amount=plan_price,
        payment_method="CASH",
        timestamp=now
    )
    db.add(sale)

    db.commit()

    # 5. Open Internet in firewall
    firewall.allow_client(client_ip, client_mac)

    return active_session, action_msg

def activate_free_trial(
    db: Session,
    client_ip: str,
    client_mac: Optional[str] = None,
    device_info: Optional[str] = None
) -> WifiSession:
    """
    Grants a one-time free trial (e.g. 5 minutes) per device MAC.
    """
    if not settings.FREE_TRIAL_ENABLED:
        raise ValueError("La prueba gratuita está desactivada en este momento.")

    mac_key = client_mac if (client_mac and client_mac != "UNKNOWN_MAC") else f"IP_{client_ip}"

    # Check if MAC already used trial
    existing_trial = db.query(TrialRecord).filter(TrialRecord.mac_address == mac_key).first()
    if existing_trial:
        raise ValueError("Este dispositivo ya utilizó su prueba gratuita de internet.")

    now = utc_now()
    duration = settings.FREE_TRIAL_MINUTES

    # Create trial session
    new_session = WifiSession(
        voucher_id=None,
        client_ip=client_ip,
        client_mac=client_mac,
        device_info=device_info,
        started_at=now,
        expires_at=now + timedelta(minutes=duration),
        total_minutes=duration,
        status=SessionStatus.ACTIVE
    )
    db.add(new_session)

    trial_log = TrialRecord(
        mac_address=mac_key,
        client_ip=client_ip,
        used_at=now
    )
    db.add(trial_log)
    db.commit()

    # Open firewall
    firewall.allow_client(client_ip, client_mac)

    return new_session

def get_active_session(db: Session, client_ip: str) -> Optional[WifiSession]:
    """
    Returns active session for client IP if not expired.
    """
    now = utc_now()
    session = db.query(WifiSession).filter(
        WifiSession.client_ip == client_ip,
        WifiSession.status == SessionStatus.ACTIVE
    ).order_by(WifiSession.started_at.desc()).first()

    if session:
        # Check if already expired
        exp = session.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            # Mark expired immediately
            session.status = SessionStatus.EXPIRED
            session.ended_at = now
            db.commit()
            firewall.revoke_client(session.client_ip, session.client_mac)
            return None
        return session

    return None

def check_and_expire_sessions(db: Session) -> int:
    """
    Background worker task: Finds all sessions past their expires_at
    and revokes their internet access immediately!
    """
    now = utc_now()
    expired_sessions = db.query(WifiSession).filter(
        WifiSession.status == SessionStatus.ACTIVE,
        WifiSession.expires_at <= now
    ).all()

    revoked_count = 0
    for sess in expired_sessions:
        sess.status = SessionStatus.EXPIRED
        sess.ended_at = now
        firewall.revoke_client(sess.client_ip, sess.client_mac)
        revoked_count += 1

    if revoked_count > 0:
        db.commit()

    return revoked_count

def manual_revoke_session(db: Session, session_id: str) -> bool:
    """
    Admin action to manually disconnect a user.
    """
    sess = db.query(WifiSession).filter(WifiSession.id == session_id).first()
    if sess and sess.status == SessionStatus.ACTIVE:
        sess.status = SessionStatus.REVOKED
        sess.ended_at = utc_now()
        db.commit()
        firewall.revoke_client(sess.client_ip, sess.client_mac)
        return True
    return False

def add_time_to_session(db: Session, session_id: str, minutes: int) -> Optional[WifiSession]:
    """
    Admin action to gift or extend minutes for an active user.
    """
    sess = db.query(WifiSession).filter(WifiSession.id == session_id).first()
    if sess:
        now = utc_now()
        # If expired, reactivate from now
        if sess.status != SessionStatus.ACTIVE or sess.expires_at <= now:
            sess.status = SessionStatus.ACTIVE
            sess.expires_at = now + timedelta(minutes=minutes)
        else:
            sess.expires_at = sess.expires_at + timedelta(minutes=minutes)

        sess.total_minutes += minutes
        db.commit()
        firewall.allow_client(sess.client_ip, sess.client_mac)
        return sess
    return None
