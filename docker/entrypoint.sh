#!/usr/bin/env bash
# ==============================================================================
# Docker Container Entrypoint: Network Orchestrator + Ticketing POS Backend
# ==============================================================================
set -euo pipefail

INTERFACE="${INTERFACE:-wlan0}"
HOST_IP="${HOST_IP:-192.168.4.1}"
NETMASK="${NETMASK:-255.255.255.0}"
DHCP_START="${DHCP_START:-192.168.4.50}"
DHCP_END="${DHCP_END:-192.168.4.200}"
ENABLE_NETWORK_SETUP="${ENABLE_NETWORK_SETUP:-true}"

cleanup() {
  echo "[DOCKER SHUTDOWN] Terminating container services..."
  if [ "$ENABLE_NETWORK_SETUP" = "true" ]; then
    echo "Cleaning iptables redirect rules..."
    iptables -t nat -D PREROUTING -i "$INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null || true
    iptables -D INPUT -i "$INTERFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || true
    iptables -D INPUT -i "$INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || true
    iptables -D INPUT -i "$INTERFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

    echo "Stopping dnsmasq..."
    pkill -f "dnsmasq.*network/dnsmasq.conf" 2>/dev/null || true
  fi
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

echo "=========================================================="
echo " Starting Dockerized Ticketing & Captive Portal System"
echo " Host IP    : $HOST_IP"
echo " Interface  : $INTERFACE"
echo " Network Opt: ENABLE_NETWORK_SETUP=$ENABLE_NETWORK_SETUP"
echo "=========================================================="

if [ "$ENABLE_NETWORK_SETUP" = "true" ]; then
  # 1. Bring interface up and assign static IP if not already set
  echo "[1/4] Ensuring interface $INTERFACE has IP $HOST_IP..."
  ip link set dev "$INTERFACE" up 2>/dev/null || true
  if ! ip addr show dev "$INTERFACE" | grep -q "$HOST_IP"; then
    echo "Assigning $HOST_IP/24 to $INTERFACE..."
    ip addr add "$HOST_IP/24" dev "$INTERFACE" 2>/dev/null || true
  fi

  # 2. Enable kernel packet forwarding
  echo "[2/4] Enabling IPv4 forwarding..."
  sysctl -w net.ipv4.ip_forward=1 2>/dev/null || true

  # 3. iptables PREROUTING redirect (80 -> 8000)
  echo "[3/4] Configuring iptables port forwarding (80 -> 8000)..."
  if ! iptables -t nat -C PREROUTING -i "$INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null; then
    iptables -t nat -A PREROUTING -i "$INTERFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000
  fi
  iptables -C INPUT -i "$INTERFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$INTERFACE" -p udp --dport 53 -j ACCEPT
  iptables -C INPUT -i "$INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$INTERFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT
  iptables -C INPUT -i "$INTERFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$INTERFACE" -p tcp --dport 8000 -j ACCEPT

  # 4. Generate dnsmasq configuration from template & launch
  echo "[4/4] Launching dnsmasq DHCP & Wildcard DNS..."
  sed \
    -e "s|__INTERFACE__|$INTERFACE|g" \
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
