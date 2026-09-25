import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models import Plan, Voucher, Session as WifiSession, VoucherStatus, SessionStatus
from app.services import session_manager

client = TestClient(app, follow_redirects=False)

@pytest.fixture(scope="session", autouse=True)
def ensure_test_plan():
    db = SessionLocal()
    plan = db.query(Plan).filter(Plan.name == "1 Hora de Conexión").first()
    if not plan:
        plan = Plan(name="1 Hora de Conexión", duration_minutes=60, price=0.50, description="Test plan")
        db.add(plan)
        db.commit()
    db.close()

def create_test_voucher(duration: int = 60) -> str:
    db = SessionLocal()
    plan = db.query(Plan).first()
    test_pin = f"T{uuid.uuid4().hex[:5].upper()}"
    v = Voucher(
        pin=test_pin,
        plan_id=plan.id,
        duration_minutes=duration,
        status=VoucherStatus.AVAILABLE
    )
    db.add(v)
    db.commit()
    db.close()
    return test_pin

def test_captive_portal_landing_page():
    """Verify landing page renders the PIN login form."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Internet Wi-Fi Hotspot" in res.text
    assert "CÓDIGO PIN" in res.text

def test_pin_redemption_and_internet_grant():
    """
    Test buying and activating an internet PIN:
    1. Enter PIN
    2. Verify internet access granted and session started
    3. Check status API returns active with countdown
    4. Attempting to use same PIN again must fail
    """
    pin = create_test_voucher(60)

    # 1. Connect with generated PIN
    res = client.post("/api/connect", json={"pin": pin})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["total_minutes"] >= 60
    assert data["remaining_seconds"] > 3500

    # 2. Check status poll
    status_res = client.get("/api/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["is_active"] is True
    assert status_data["remaining_seconds"] > 3500

    # 3. Attempting duplicate PIN reuse must be rejected
    res_dup = client.post("/api/connect", json={"pin": pin})
    assert res_dup.status_code == 400
    assert "ya fue utilizada" in res_dup.json()["detail"]

def test_recharge_and_time_topup():
    """
    Verify that entering a second PIN while already active
    adds more minutes to the current connection without interrupting it!
    """
    recharge_pin = create_test_voucher(30)
    res = client.post("/api/connect", json={"pin": recharge_pin})
    assert res.status_code == 200
    data = res.json()
    assert data["remaining_seconds"] > 5000

def test_session_expiration_revocation():
    """
    Verify that when session time expires:
    1. Status changes to EXPIRED
    2. Internet access is revoked
    3. Status API reports inactive
    """
    db = SessionLocal()
    # Expire all active test sessions
    sessions = db.query(WifiSession).filter(WifiSession.status == SessionStatus.ACTIVE).all()
    for s in sessions:
        s.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    # Run background session expiration check
    expired_count = session_manager.check_and_expire_sessions(db)
    assert expired_count >= 1
    db.close()

    # Now poll status API
    status_res = client.get("/api/status")
    assert status_res.status_code == 200
    assert status_res.json()["is_active"] is False

def test_admin_vouchers_and_monitoring():
    """Verify admin batch generation and active connections table."""
    db = SessionLocal()
    plan = db.query(Plan).first()
    plan_id = plan.id
    db.close()

    gen_res = client.post("/api/admin/vouchers/generate", json={"plan_id": plan_id, "quantity": 5})
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["total_generated"] == 5
    assert len(gen_data["vouchers"]) == 5

    # Check stats
    stats_res = client.get("/api/admin/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["vouchers_available"] >= 5
    assert stats["total_revenue"] >= 0
