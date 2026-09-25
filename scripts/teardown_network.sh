#!/usr/bin/env bash
# ==============================================================================
# Hotspot Internet Billing: Network & Gateway Teardown Script
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] Este script debe ejecutarse como root (ej: sudo ./scripts/teardown_network.sh)"
  exit 1
fi

HOTSPOT_IFACE="${1:-wlan0}"
WAN_IFACE="${2:-eth0}"
HOST_IP="${3:-192.168.4.1}"

echo "=========================================================="
echo " Restaurando Reglas de Red y Deteniendo Hotspot Gateway"
echo "=========================================================="

# 1. Detener dnsmasq
if [ -f /run/ticketing_dnsmasq.pid ]; then
  kill "$(cat /run/ticketing_dnsmasq.pid)" 2>/dev/null || true
  rm -f /run/ticketing_dnsmasq.pid
fi
pkill -f "dnsmasq.*network/dnsmasq.conf" 2>/dev/null || true

# 2. Limpiar iptables
iptables -t nat -D POSTROUTING -o "$WAN_IFACE" -j MASQUERADE 2>/dev/null || true
iptables -t nat -D PREROUTING -i "$HOTSPOT_IFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null || true
iptables -D FORWARD -i "$HOTSPOT_IFACE" -j DROP 2>/dev/null || true
iptables -D INPUT -i "$HOTSPOT_IFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -D INPUT -i "$HOTSPOT_IFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || true
iptables -D INPUT -i "$HOTSPOT_IFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

# 3. Remover IP estática del Hotspot
ip addr del "$HOST_IP/24" dev "$HOTSPOT_IFACE" 2>/dev/null || true

echo "[ÉXITO] Red restaurada correctamente."
