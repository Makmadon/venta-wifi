import hmac
import hashlib
from app.config import settings

def generate_ticket_hash(ticket_id: str, event_id: int, buyer_name: str) -> str:
    """
    Generate a cryptographic HMAC-SHA256 hash for ticket verification.
    This guarantees that tickets cannot be forged or tampered with even
    in an offline environment without external validation services.
    """
    normalized_name = (buyer_name or "").strip().lower()
    payload = f"{ticket_id}:{event_id}:{normalized_name}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()

def verify_ticket_signature(ticket_id: str, event_id: int, buyer_name: str, candidate_hash: str) -> bool:
    """
    Verify whether a candidate hash matches the authentic HMAC signature.
    Uses hmac.compare_digest to prevent timing attacks.
    """
    expected_hash = generate_ticket_hash(ticket_id, event_id, buyer_name)
    return hmac.compare_digest(expected_hash, candidate_hash)
