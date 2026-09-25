#!/usr/bin/env bash
# ==============================================================================
# Network & Captive Interception Teardown Script
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] This script must be run as root (e.g., sudo ./scripts/teardown_network.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_CONF="$PROJECT_ROOT/network/dnsmasq.conf"

INTERFACE="${1:-wlan0}"
HOST_IP="${2:-192.168.4.1}"

echo "=========================================================="
echo " Tearing down Captive Portal Network & Firewall Rules"
echo "=========================================================="

# 1. Stop custom dnsmasq
echo "[1/3] Stopping dnsmasq instance..."
if [ -f /run/ticketing_dnsmasq.pid ]; then
  kill "$(cat /run/ticketing_dnsmasq.pid)" 2>/dev/null || true
  rm -f /run/ticketing_dnsmasq.pid
fi
pkill -f "dnsmasq.*$OUTPUT_CONF" 2>/dev/null || true

# 2. Remove iptables rules
echo "[2/3] Cleaning iptables NAT and filter rules..."
iptables -t nat -D PREROUTING -i "$INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null || true
iptables -D INPUT -i "$INTERFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || true
iptables -D INPUT -i "$INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || true
iptables -D INPUT -i "$INTERFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

# 3. Remove assigned static IP
echo "[3/3] Removing $HOST_IP/24 from interface $INTERFACE..."
ip addr del "$HOST_IP/24" dev "$INTERFACE" 2>/dev/null || true

echo "[SUCCESS] Network teardown complete."
