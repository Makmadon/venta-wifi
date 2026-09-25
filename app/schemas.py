from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# --- Event Schemas ---
class EventBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    total_capacity: int = Field(..., gt=0)
    price: float = Field(..., ge=0.0)

class EventCreate(EventBase):
    has_seat_numbers: bool = False
    seat_prefix: str = "A"

class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    available_tickets: int = 0
    sold_tickets: int = 0

# --- Ticket Schemas ---
class TicketBase(BaseModel):
    id: str
    event_id: int
    seat_number: Optional[str] = None
    status: str

class TicketResponse(TicketBase):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    reserved_at: Optional[datetime] = None

class TicketDetailResponse(TicketBase):
    model_config = ConfigDict(from_attributes=True)

    buyer_name: Optional[str] = None
    buyer_contact: Optional[str] = None
    qr_hash: Optional[str] = None
    used_at: Optional[datetime] = None
    created_at: datetime
    event_title: Optional[str] = None
    event_price: Optional[float] = None
    qr_base64: Optional[str] = None

class SeatStatus(BaseModel):
    id: str
    seat_number: str
    status: str

# --- Purchase & Transaction Schemas ---
class PurchaseRequest(BaseModel):
    event_id: int
    ticket_id: Optional[str] = None
    quantity: int = Field(default=1, ge=1, le=10)
    buyer_name: str = Field(..., min_length=2, max_length=120)
    buyer_contact: str = Field(..., min_length=3, max_length=120)
    payment_method: str = Field(default="CASH", max_length=50)

class PurchaseResponse(BaseModel):
    success: bool
    message: str
    tickets: List[TicketDetailResponse]
    total_amount: float

# --- Verification Schemas ---
class VerifyRequest(BaseModel):
    code: str = Field(..., min_length=4)

class VerifyResponse(BaseModel):
    status: str  # "VALID", "ALREADY_USED", "INVALID"
    message: str
    ticket: Optional[TicketDetailResponse] = None

# --- Admin Statistics ---
class AdminStatsResponse(BaseModel):
    total_events: int
    total_tickets: int
    sold_tickets: int
    used_tickets: int
    available_tickets: int
    total_revenue: float
