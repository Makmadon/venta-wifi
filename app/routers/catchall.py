from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from app.config import settings

router = APIRouter(tags=["Catch-All Wildcard"])

@router.api_route("/{full_path:path}", methods=["GET", "HEAD"], status_code=status.HTTP_302_FOUND)
def catch_all_redirect(full_path: str, request: Request):
    """
    Catch-all router: Any unrecognized path requested by captive clients
    (e.g., trying to access any website over HTTP) will be intercepted and
    redirected safely to the ticketing captive portal root.
    """
    # Prevent redirection loops if root is requested
    if not full_path or full_path == "/":
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    return RedirectResponse(url=f"http://{settings.HOST_IP}/", status_code=status.HTTP_302_FOUND)
