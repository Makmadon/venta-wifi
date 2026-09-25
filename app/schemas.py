from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# --- Plan Schemas ---
class PlanBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    duration_minutes: int = Field(..., gt=0)
    price: float = Field(..., ge=0.0)
    description: Optional[str] = None

class PlanCreate(PlanBase):
    pass

class PlanResponse(PlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime

# --- Voucher Schemas ---
class VoucherGenerateRequest(BaseModel):
    plan_id: int
    quantity: int = Field(default=10, ge=1, le=200)

class VoucherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pin: str
    plan_id: int
    duration_minutes: int
    status: str
    created_at: datetime
    used_at: Optional[datetime] = None

class VoucherCard(BaseModel):
    pin: str
    plan_name: str
    duration_minutes: int
    price: float
    qr_data: str

class VoucherBatchResponse(BaseModel):
    total_generated: int
    plan_name: str
    duration_minutes: int
    price: float
    vouchers: List[VoucherCard]

# --- Connection & Session Schemas ---
class ConnectRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=16)

class ConnectResponse(BaseModel):
    success: bool
    message: str
    session_id: str
    expires_at: datetime
    remaining_seconds: int
    total_minutes: int

class SessionStatusResponse(BaseModel):
    is_active: bool
    remaining_seconds: int
    expires_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    total_minutes: Optional[int] = 0
    client_ip: str
    message: Optional[str] = None

class AdminSessionItem(BaseModel):
    id: str
    client_ip: str
    client_mac: Optional[str] = None
    pin: Optional[str] = None
    started_at: str
    expires_at: str
    remaining_seconds: int
    status: str
    device_info: Optional[str] = None

# --- Admin Statistics ---
class AdminHotspotStats(BaseModel):
    active_sessions: int
    vouchers_available: int
    vouchers_sold: int
    total_revenue: float
