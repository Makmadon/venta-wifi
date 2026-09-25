import os
import subprocess
import logging
from typing import Set
from app.config import settings

logger = logging.getLogger("firewall")
logger.setLevel(logging.INFO)

# Track active authorized IPs in memory
_authorized_ips: Set[str] = set()

def is_root() -> bool:
    return os.geteuid() == 0

def get_firewall_mode() -> str:
    if settings.FIREWALL_MODE == "simulated":
        return "simulated"
    if settings.FIREWALL_MODE == "iptables":
        return "iptables"
    # Auto: use iptables only if root
    return "iptables" if is_root() else "simulated"

def allow_client(client_ip: str, client_mac: str = None) -> bool:
    """
    Dynamically authorizes a device to access the external internet.
    """
    mode = get_firewall_mode()
    _authorized_ips.add(client_ip)
    logger.info(f"[{mode.upper()}] GRANTING INTERNET ACCESS -> IP: {client_ip}, MAC: {client_mac}")

    if mode == "iptables":
        try:
            iface = settings.HOTSPOT_INTERFACE
            # 1. Bypass HTTP captive redirect for this authenticated IP
            subprocess.run([
                "iptables", "-t", "nat", "-I", "PREROUTING", "1",
                "-i", iface, "-s", client_ip, "-p", "tcp", "--dport", "80", "-j", "ACCEPT"
            ], check=False, stderr=subprocess.DEVNULL)

            # 2. Allow forwarding to/from WAN for this IP
            subprocess.run([
                "iptables", "-I", "FORWARD", "1",
                "-i", iface, "-s", client_ip, "-j", "ACCEPT"
            ], check=False, stderr=subprocess.DEVNULL)
            
            subprocess.run([
                "iptables", "-I", "FORWARD", "1",
                "-o", iface, "-d", client_ip, "-j", "ACCEPT"
            ], check=False, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logger.error(f"Error allowing client in iptables: {e}")
            return False

    return True

def revoke_client(client_ip: str, client_mac: str = None) -> bool:
    """
    Revokes internet access when a client's prepaid time has expired.
    Traffic is immediately blocked and intercepted back to the captive portal.
    """
    mode = get_firewall_mode()
    _authorized_ips.discard(client_ip)
    logger.info(f"[{mode.upper()}] REVOKING INTERNET ACCESS (TIME EXPIRED) -> IP: {client_ip}, MAC: {client_mac}")

    if mode == "iptables":
        try:
            iface = settings.HOTSPOT_INTERFACE
            # 1. Remove bypass rule
            subprocess.run([
                "iptables", "-t", "nat", "-D", "PREROUTING",
                "-i", iface, "-s", client_ip, "-p", "tcp", "--dport", "80", "-j", "ACCEPT"
            ], check=False, stderr=subprocess.DEVNULL)

            # 2. Remove forward allow rules
            subprocess.run([
                "iptables", "-D", "FORWARD",
                "-i", iface, "-s", client_ip, "-j", "ACCEPT"
            ], check=False, stderr=subprocess.DEVNULL)

            subprocess.run([
                "iptables", "-D", "FORWARD",
                "-o", iface, "-d", client_ip, "-j", "ACCEPT"
            ], check=False, stderr=subprocess.DEVNULL)

            # 3. Kill active tracked connections for this IP
            subprocess.run(["conntrack", "-D", "-s", client_ip], check=False, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            logger.error(f"Error revoking client in iptables: {e}")
            return False

    return True

def is_client_authorized(client_ip: str) -> bool:
    return client_ip in _authorized_ips

def get_arp_mac(client_ip: str) -> str:
    """
    Attempts to read device MAC address from Linux ARP cache (/proc/net/arp).
    """
    try:
        with open("/proc/net/arp", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[0] == client_ip:
                    mac = parts[3]
                    if mac != "00:00:00:00:00:00":
                        return mac.upper()
    except Exception:
        pass
    return "UNKNOWN_MAC"
