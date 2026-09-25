import os
import subprocess
import shutil
from typing import Dict, Any, List

def get_device_model() -> str:
    """Detects Raspberry Pi model, Laptop model, or generic Linux machine."""
    for dt_path in ["/proc/device-tree/model", "/sys/firmware/devicetree/base/model"]:
        if os.path.exists(dt_path):
            try:
                with open(dt_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read().replace("\x00", "").strip()
            except Exception:
                pass

    dmi_path = "/sys/class/dmi/id/product_name"
    if os.path.exists(dmi_path):
        try:
            with open(dmi_path, "r", encoding="utf-8", errors="ignore") as f:
                name = f.read().strip()
                if name:
                    return f"PC / Laptop ({name})"
        except Exception:
            pass

    return "Equipo Linux Genérico"

def is_raspberry_pi() -> bool:
    model = get_device_model().lower()
    return "raspberry" in model

def get_network_interfaces() -> List[Dict[str, str]]:
    """List network interfaces with IP and type."""
    interfaces = []
    try:
        r = subprocess.run(["ip", "-br", "addr", "show"], capture_output=True, text=True, check=False)
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0]
                state = parts[1]
                ip = parts[2].split("/")[0] if len(parts) >= 3 else "Sin IP"
                if name.startswith("wl"):
                    iface_type = "Wi-Fi (Inalámbrica)"
                elif name.startswith("en") or name.startswith("eth"):
                    iface_type = "Ethernet (Cable)"
                elif name.startswith("usb"):
                    iface_type = "USB Tethering"
                elif name == "lo":
                    continue
                else:
                    iface_type = "Virtual / Bridge"

                interfaces.append({
                    "name": name,
                    "state": state,
                    "ip": ip,
                    "type": iface_type
                })
    except Exception:
        pass
    return interfaces

def check_wifi_capabilities() -> Dict[str, Any]:
    """
    Inspects mac80211 wireless driver capabilities to determine if the card
    can act as an AP (Access Point) and if it supports Simultaneous Dual STA+AP.
    """
    model = get_device_model()
    is_rpi = is_raspberry_pi()
    has_ap = False
    has_dual_sta_ap = False
    details = ""

    if shutil.which("iw"):
        try:
            r = subprocess.run(["iw", "list"], capture_output=True, text=True, check=False)
            out = r.stdout

            # Check AP support
            if "* AP" in out or " AP\n" in out:
                has_ap = True

            # Check Simultaneous STA + AP combination
            if "valid interface combinations" in out:
                comb_section = out.split("valid interface combinations:")[1]
                if "HT Capability" in comb_section:
                    comb_section = comb_section.split("HT Capability")[0]
                
                for block in comb_section.split("*"):
                    if "managed" in block and "AP" in block:
                        has_dual_sta_ap = True
                        break
        except Exception as e:
            details = f"Error al consultar iw: {e}"

    # Determine recommended mode
    if is_rpi:
        # Raspberry Pi Broadcom Wi-Fi usually performs best with Ethernet WAN + Wi-Fi Hotspot
        recommended_mode = "Ethernet (eth0) + Wi-Fi Hotspot (wlan0)"
        details = (
            "En Raspberry Pi (3, 4, 5) el chip integrado Broadcom soporta modo AP, "
            "pero para máxima estabilidad y evitar caída de velocidad, la mejor práctica "
            "es conectar la Pi por cable de red (eth0) al router y emitir el Wi-Fi por wlan0."
        )
    elif has_dual_sta_ap:
        recommended_mode = "Modo Dual Virtual AP (STA + AP Simultáneos)"
        details = (
            "¡Tu tarjeta soporta Modo Dual! Puede emitir el Hotspot Wi-Fi para clientes "
            "mientras permanece conectada a tu red Wi-Fi de internet en el mismo canal."
        )
    elif has_ap:
        recommended_mode = "Punto de Acceso Exclusivo (Requiere Internet por Cable o USB)"
        details = (
            "Tu tarjeta soporta modo Hotspot AP, pero no simultáneo en un solo canal. "
            "Debes recibir internet por cable Ethernet (eth0) o USB y emitir por Wi-Fi."
        )
    else:
        recommended_mode = "Router Wi-Fi Externo Requerido"
        details = "No se detectó soporte para AP nativo en la tarjeta inalámbrica. Se recomienda usar un router externo."

    return {
        "device_model": model,
        "is_raspberry_pi": is_rpi,
        "has_ap_support": has_ap,
        "has_dual_sta_ap_support": has_dual_sta_ap,
        "recommended_mode": recommended_mode,
        "details": details,
        "interfaces": get_network_interfaces()
    }

def print_hardware_summary():
    """Prints a friendly summary in the terminal console on startup."""
    info = check_wifi_capabilities()
    print("\n" + "=" * 60)
    print(" [DIAGNÓSTICO DE HARDWARE PARA HOTSPOT]")
    print(f" • Dispositivo Detectado : {info['device_model']}")
    print(f" • ¿Es Raspberry Pi?     : {'SÍ' if info['is_raspberry_pi'] else 'NO'}")
    print(f" • Soporte Modo AP       : {'SÍ (Puede emitir Wi-Fi)' if info['has_ap_support'] else 'NO'}")
    print(f" • Soporte Dual STA+AP   : {'SÍ (Virtual AP simultáneo)' if info['has_dual_sta_ap_support'] else 'NO'}")
    print(f" • Modo Recomendado      : {info['recommended_mode']}")
    print(f" • Nota Técnica          : {info['details']}")
    print("=" * 60 + "\n")
