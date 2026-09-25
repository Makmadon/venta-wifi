#!/usr/bin/env bash
# ==============================================================================
# Docker Container Entrypoint: Network Orchestrator + Ticketing POS Backend
# ==============================================================================
set -euo pipefail

HOTSPOT_INTERFACE="${HOTSPOT_INTERFACE:-${INTERFACE:-wlan0}}"
WAN_INTERFACE="${WAN_INTERFACE:-eth0}"
HOST_IP="${HOST_IP:-192.168.4.1}"
NETMASK="${NETMASK:-255.255.255.0}"
DHCP_START="${DHCP_START:-192.168.4.50}"
DHCP_END="${DHCP_END:-192.168.4.200}"
ENABLE_NETWORK_SETUP="${ENABLE_NETWORK_SETUP:-false}"

cleanup() {
  echo "[DOCKER SHUTDOWN] Terminating container services..."
  if [ "$ENABLE_NETWORK_SETUP" = "true" ]; then
    echo "Cleaning iptables redirect rules..."
    iptables -t nat -D POSTROUTING -o "$WAN_IFACE" -j MASQUERADE 2>/dev/null || true
    iptables -t nat -D PREROUTING -i "$HOTSPOT_INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null || true
    iptables -D FORWARD -i "$HOTSPOT_INTERFACE" -j DROP 2>/dev/null || true
    iptables -D INPUT -i "$HOTSPOT_INTERFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || true
    iptables -D INPUT -i "$HOTSPOT_INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || true
    iptables -D INPUT -i "$HOTSPOT_INTERFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

    echo "Stopping dnsmasq..."
    pkill -f "dnsmasq.*network/dnsmasq.conf" 2>/dev/null || true
  fi
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo "=========================================================="
echo " Starting Dockerized Internet Billing & Hotspot Gateway"
echo " Hotspot Interface : $HOTSPOT_INTERFACE"
echo " WAN Interface     : $WAN_INTERFACE"
echo " Host IP           : $HOST_IP"
echo " Network Setup     : ENABLE_NETWORK_SETUP=$ENABLE_NETWORK_SETUP"
echo "=========================================================="

if [ "$ENABLE_NETWORK_SETUP" = "true" ]; then
  echo "[1/5] Ensuring interface $HOTSPOT_INTERFACE has IP $HOST_IP..."
  ip link set dev "$HOTSPOT_INTERFACE" up 2>/dev/null || true
  if ! ip addr show dev "$HOTSPOT_INTERFACE" | grep -q "$HOST_IP"; then
    echo "Assigning $HOST_IP/24 to $HOTSPOT_INTERFACE..."
    ip addr add "$HOST_IP/24" dev "$HOTSPOT_INTERFACE" 2>/dev/null || true
  fi

  echo "[2/5] Enabling IPv4 forwarding..."
  sysctl -w net.ipv4.ip_forward=1 2>/dev/null || true

  echo "[3/5] Configuring NAT Masquerade to $WAN_INTERFACE..."
  if ! iptables -t nat -C POSTROUTING -o "$WAN_INTERFACE" -j MASQUERADE 2>/dev/null; then
    iptables -t nat -A POSTROUTING -o "$WAN_INTERFACE" -j MASQUERADE
  fi

  echo "[4/5] Applying captive portal firewall rules..."
  if ! iptables -t nat -C PREROUTING -i "$HOTSPOT_INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null; then
    iptables -t nat -A PREROUTING -i "$HOTSPOT_INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000
  fi
  iptables -C INPUT -i "$HOTSPOT_INTERFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$HOTSPOT_INTERFACE" -p udp --dport 53 -j ACCEPT
  iptables -C INPUT -i "$HOTSPOT_INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$HOTSPOT_INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT
  iptables -C INPUT -i "$HOTSPOT_INTERFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$HOTSPOT_INTERFACE" -p tcp --dport 8000 -j ACCEPT

  if ! iptables -C FORWARD -i "$HOTSPOT_INTERFACE" -j DROP 2>/dev/null; then
    iptables -A FORWARD -i "$HOTSPOT_INTERFACE" -j DROP
  fi

  echo "[5/5] Launching dnsmasq DHCP & Wildcard DNS..."
  sed \
    -e "s|__INTERFACE__|$HOTSPOT_INTERFACE|g" \
    -e "s|__HOST_IP__|$HOST_IP|g" \
    -e "s|__NETMASK__|$NETMASK|g" \
    -e "s|__DHCP_START__|$DHCP_START|g" \
    -e "s|__DHCP_END__|$DHCP_END|g" \
    /app/network/dnsmasq.conf.template > /app/network/dnsmasq.conf

  pkill -f "dnsmasq.*network/dnsmasq.conf" 2>/dev/null || true
  dnsmasq -C /app/network/dnsmasq.conf
fi

# 5. Populate initial database if empty
echo "Checking and seeding database..."
python /app/scripts/seed_data.py

echo "=========================================================="
echo " Application ready! Starting Uvicorn on 0.0.0.0:8000"
echo "=========================================================="
exec uvicorn main:app --host 0.0.0.0 --port 8000
