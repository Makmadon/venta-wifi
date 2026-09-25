import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app, follow_redirects=False)

def test_portal_homepage():
    """Verify that root landing page serves HTTP 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Internet Wi-Fi Hotspot" in response.text

def test_android_cna_probes():
    """Verify Android generate_204 probes redirect to portal."""
    r1 = client.get("/generate_204")
    assert r1.status_code == 302
    assert "192.168.4.1" in r1.headers["location"]

    r2 = client.get("/gen_204")
    assert r2.status_code == 302
    assert "192.168.4.1" in r2.headers["location"]

def test_apple_cna_probes():
    """Verify Apple hotspot-detect probe redirects to portal."""
    r = client.get("/hotspot-detect.html")
    assert r.status_code == 302
    assert "192.168.4.1" in r.headers["location"]

def test_windows_ncsi_probes():
    """Verify Windows NCSI probes redirect to portal."""
    r1 = client.get("/ncsi.txt")
    assert r1.status_code == 302
    assert "192.168.4.1" in r1.headers["location"]

    r2 = client.get("/connecttest.txt")
    assert r2.status_code == 302
    assert "192.168.4.1" in r2.headers["location"]

def test_generic_probes():
    """Verify Firefox and Ubuntu captive probes redirect."""
    for path in ["/canonical.html", "/success.txt", "/check_network_status.txt"]:
        r = client.get(path)
        assert r.status_code == 302

def test_catch_all_wildcard():
    """Verify random external web requests redirect safely to portal."""
    r = client.get("/random/website/path.html")
    assert r.status_code == 302
    assert "192.168.4.1" in r.headers["location"]

def test_static_assets_not_intercepted():
    """Verify static assets are served directly without redirect."""
    r = client.get("/static/css/style.css")
    assert r.status_code == 200
    assert "--primary" in response_text if (response_text := r.text) else True
