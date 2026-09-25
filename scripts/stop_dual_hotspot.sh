#!/usr/bin/env bash
# ==============================================================================
# Detener Hotspot Dual y Limpiar Interfaz Virtual ap0
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] Este script debe ejecutarse como root (ej: sudo ./scripts/stop_dual_hotspot.sh)"
  exit 1
fi

STA_IFACE="${1:-wlan0}"
AP_IFACE="ap0"

echo "Limpiando servicios de Hotspot Dual..."

# 1. Matar procesos
pkill -f "hostapd.*network/hostapd.conf" 2>/dev/null || true
if [ -f /run/hotspot_dual_dnsmasq.pid ]; then
  kill "$(cat /run/hotspot_dual_dnsmasq.pid)" 2>/dev/null || true
  rm -f /run/hotspot_dual_dnsmasq.pid
fi
pkill -f "dnsmasq.*network/dnsmasq_dual.conf" 2>/dev/null || true

# 2. Limpiar iptables
iptables -t nat -D POSTROUTING -o "$STA_IFACE" -j MASQUERADE 2>/dev/null || true
iptables -t nat -D PREROUTING -i "$AP_IFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null || true
iptables -D FORWARD -i "$AP_IFACE" -j DROP 2>/dev/null || true
iptables -D INPUT -i "$AP_IFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -D INPUT -i "$AP_IFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || true
iptables -D INPUT -i "$AP_IFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

# 3. Eliminar interfaz virtual ap0
if ip link show dev "$AP_IFACE" > /dev/null 2>&1; then
  echo "Eliminando interfaz virtual $AP_IFACE..."
  iw dev "$AP_IFACE" del 2>/dev/null || true
fi

echo "[LISTO] Hotspot dual detenido y red restaurada con éxito."
