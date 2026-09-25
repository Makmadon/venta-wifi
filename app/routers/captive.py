from fastapi import APIRouter, Response, status
from fastapi.responses import RedirectResponse, HTMLResponse
from app.config import settings

router = APIRouter(tags=["Captive Portal Detection"])

PORTAL_TARGET = f"http://{settings.HOST_IP}/"

@router.api_route("/generate_204", methods=["GET", "HEAD"], status_code=status.HTTP_302_FOUND)
@router.api_route("/gen_204", methods=["GET", "HEAD"], status_code=status.HTTP_302_FOUND)
def android_probe():
    """
    Android Captive Portal Detection Probe.
    Android checks if http://clients3.google.com/generate_204 returns 204.
    Redirecting to portal forces Android to display 'Sign in to network' notification.
    """
    return RedirectResponse(url=PORTAL_TARGET, status_code=status.HTTP_302_FOUND)

@router.api_route("/hotspot-detect.html", methods=["GET", "HEAD"])
@router.api_route("/library/test/success.html", methods=["GET", "HEAD"])
def apple_cna_probe():
    """
    Apple iOS / macOS Captive Network Assistant (CNA) Probe.
    Apple probes http://captive.apple.com/hotspot-detect.html expecting 'Success'.
    Returning a redirect or captive landing triggers the native CNA sheet popup.
    """
    return RedirectResponse(url=PORTAL_TARGET, status_code=status.HTTP_302_FOUND)

@router.api_route("/ncsi.txt", methods=["GET", "HEAD"])
@router.api_route("/connecttest.txt", methods=["GET", "HEAD"])
def windows_ncsi_probe():
    """
    Microsoft Windows Network Connectivity Status Indicator (NCSI).
    Windows expects 'Microsoft Connect Test' or 'Microsoft NCSI'.
    A 302 redirect triggers the Windows browser login notification.
    """
    return RedirectResponse(url=PORTAL_TARGET, status_code=status.HTTP_302_FOUND)

@router.api_route("/canonical.html", methods=["GET", "HEAD"])
@router.api_route("/success.txt", methods=["GET", "HEAD"])
@router.api_route("/check_network_status.txt", methods=["GET", "HEAD"])
def generic_desktop_probes():
    """
    Firefox, Chrome OS, Ubuntu Network Manager probes.
    """
    return RedirectResponse(url=PORTAL_TARGET, status_code=status.HTTP_302_FOUND)
