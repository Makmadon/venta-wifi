#!/usr/bin/env bash
# ==============================================================================
# Network & Captive Interception Setup Script
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] This script must be run as root (e.g., sudo ./scripts/setup_network.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATE_FILE="$PROJECT_ROOT/network/dnsmasq.conf.template"
OUTPUT_CONF="$PROJECT_ROOT/network/dnsmasq.conf"

INTERFACE="${1:-wlan0}"
HOST_IP="${2:-192.168.4.1}"
NETMASK="255.255.255.0"
DHCP_START="192.168.4.50"
DHCP_END="192.168.4.200"

echo "=========================================================="
echo " Starting Network Orchestration & Interception Setup"
echo " Interface  : $INTERFACE"
echo " Host IP    : $HOST_IP"
echo " DHCP Range : $DHCP_START - $DHCP_END"
echo "=========================================================="

# 1. Verify network interface exists
if ! ip link show dev "$INTERFACE" > /dev/null 2>&1; then
  echo "[WARNING] Interface '$INTERFACE' does not appear active or exists."
  echo "Available network interfaces:"
  ip -br link show
  echo "Continuing with '$INTERFACE'..."
fi

# 2. Configure Interface IP and bring up
echo "[1/5] Configuring IP address $HOST_IP/24 on $INTERFACE..."
ip link set dev "$INTERFACE" up || true
# Remove previous duplicate IP if already bound
ip addr del "$HOST_IP/24" dev "$INTERFACE" 2>/dev/null || true
ip addr add "$HOST_IP/24" dev "$INTERFACE" || true

# 3. Enable Kernel IPv4 Forwarding
echo "[2/5] Enabling IPv4 packet forwarding..."
sysctl -w net.ipv4.ip_forward=1 > /dev/null

# 4. Configure iptables port forwarding (80 -> 8000)
echo "[3/5] Setting up iptables PREROUTING port forwarding (80 -> 8000)..."
# Check if PREROUTING redirect rule already exists
if ! iptables -t nat -C PREROUTING -i "$INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null; then
  iptables -t nat -A PREROUTING -i "$INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000
fi

# Allow INPUT traffic for DNS (53), DHCP (67:68), and HTTP (80/8000)
if ! iptables -C INPUT -i "$INTERFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null; then
  iptables -A INPUT -i "$INTERFACE" -p udp --dport 53 -j ACCEPT
fi
if ! iptables -C INPUT -i "$INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null; then
  iptables -A INPUT -i "$INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT
fi
if ! iptables -C INPUT -i "$INTERFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null; then
  iptables -A INPUT -i "$INTERFACE" -p tcp --dport 8000 -j ACCEPT
fi

# 5. Generate dnsmasq configuration from declarative template
echo "[4/5] Generating dnsmasq configuration from declarative template..."
sed \
  -e "s|__INTERFACE__|$INTERFACE|g" \
  -e "s|__HOST_IP__|$HOST_IP|g" \
  -e "s|__NETMASK__|$NETMASK|g" \
  -e "s|__DHCP_START__|$DHCP_START|g" \
  -e "s|__DHCP_END__|$DHCP_END|g" \
  "$TEMPLATE_FILE" > "$OUTPUT_CONF"

echo "Generated: $OUTPUT_CONF"

# 6. Stop any conflicting system dnsmasq or systemd-resolved on port 53 if needed
echo "[5/5] Managing dnsmasq process..."
# Kill existing instance of our custom dnsmasq if running
pkill -f "dnsmasq.*$OUTPUT_CONF" 2>/dev/null || true

# Test dnsmasq syntax
dnsmasq --test -C "$OUTPUT_CONF"

echo "Starting dnsmasq in background..."
dnsmasq -C "$OUTPUT_CONF" --pid-file=/run/ticketing_dnsmasq.pid

echo "=========================================================="
echo " [SUCCESS] Captive Portal Network Setup Complete!"
echo " Clients connecting to $INTERFACE will receive:"
echo "   IP in range   : $DHCP_START - $DHCP_END"
echo "   Gateway & DNS : $HOST_IP"
echo "   HTTP Port 80  : Redirected to FastAPI on port 8000"
echo "=========================================================="
