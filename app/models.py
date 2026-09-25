import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class SessionStatus:
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

class VoucherStatus:
    AVAILABLE = "AVAILABLE"
    USED = "USED"
    EXPIRED = "EXPIRED"

class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    duration_minutes = Column(Integer, nullable=False)  # 15, 60, 180, 1440, etc.
    price = Column(Float, nullable=False, default=0.0)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    vouchers = relationship("Voucher", back_populates="plan", cascade="all, delete-orphan")

class Voucher(Base):
    __tablename__ = "vouchers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    pin = Column(String(16), unique=True, index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default=VoucherStatus.AVAILABLE, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by_ip = Column(String(50), nullable=True)
    used_by_mac = Column(String(50), nullable=True)

    plan = relationship("Plan", back_populates="vouchers")
    sessions = relationship("Session", back_populates="voucher")

    __table_args__ = (
        Index("idx_voucher_plan_status", "plan_id", "status"),
    )

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    voucher_id = Column(String(36), ForeignKey("vouchers.id", ondelete="SET NULL"), nullable=True)
    client_ip = Column(String(50), nullable=False, index=True)
    client_mac = Column(String(50), nullable=True, index=True)
    device_info = Column(String(255), nullable=True)
    started_at = Column(DateTime, default=utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    total_minutes = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default=SessionStatus.ACTIVE, index=True)
    ended_at = Column(DateTime, nullable=True)

    voucher = relationship("Voucher", back_populates="sessions")

    def remaining_seconds(self) -> int:
        now = utc_now()
        # Ensure aware datetime
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        rem = int((exp - now).total_seconds())
        return max(0, rem)

class TrialRecord(Base):
    __tablename__ = "trial_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac_address = Column(String(50), unique=True, index=True, nullable=False)
    client_ip = Column(String(50), nullable=False)
    used_at = Column(DateTime, default=utc_now, nullable=False)

class Sale(Base):
    __tablename__ = "sales"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    voucher_id = Column(String(36), nullable=True)
    plan_name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), default="CASH")
    timestamp = Column(DateTime, default=utc_now, nullable=False)
