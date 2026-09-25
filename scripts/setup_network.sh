#!/usr/bin/env bash
# ==============================================================================
# Hotspot Internet Billing: Network & Captive Gateway Setup Script
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] Este script debe ejecutarse como root (ej: sudo ./scripts/setup_network.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATE_FILE="$PROJECT_ROOT/network/dnsmasq.conf.template"
OUTPUT_CONF="$PROJECT_ROOT/network/dnsmasq.conf"

HOTSPOT_IFACE="${1:-wlan0}"        # Interfaz donde se conectan los clientes
WAN_IFACE="${2:-eth0}"             # Interfaz que tiene la conexión a Internet
HOST_IP="${3:-192.168.4.1}"        # IP Gateway para los clientes
NETMASK="255.255.255.0"
DHCP_START="192.168.4.50"
DHCP_END="192.168.4.200"

echo "=========================================================="
echo " Iniciando Gateway de Venta de Internet Wi-Fi"
echo " Interfaz Clientes (Hotspot) : $HOTSPOT_IFACE"
echo " Interfaz Internet (WAN)     : $WAN_IFACE"
echo " IP Gateway del Servidor     : $HOST_IP"
echo " Rango DHCP                  : $DHCP_START - $DHCP_END"
echo "=========================================================="

# 1. Asignar IP al Hotspot
echo "[1/5] Configurando IP $HOST_IP/24 en $HOTSPOT_IFACE..."
ip link set dev "$HOTSPOT_IFACE" up || true
ip addr del "$HOST_IP/24" dev "$HOTSPOT_IFACE" 2>/dev/null || true
ip addr add "$HOST_IP/24" dev "$HOTSPOT_IFACE" || true

# 2. Habilitar reenvío IPv4 en el Kernel
echo "[2/5] Habilitando reenvío de paquetes IPv4..."
sysctl -w net.ipv4.ip_forward=1 > /dev/null

# 3. Configurar NAT / Masquerade hacia la salida a internet
echo "[3/5] Configurando NAT Masquerade hacia $WAN_IFACE..."
if ! iptables -t nat -C POSTROUTING -o "$WAN_IFACE" -j MASQUERADE 2>/dev/null; then
  iptables -t nat -A POSTROUTING -o "$WAN_IFACE" -j MASQUERADE
fi

# 4. Reglas del Portal Cautivo:
# Por defecto, el tráfico de los clientes NO autorizados está bloqueado hacia internet.
# El backend de FastAPI insertará reglas ACCEPT dinámicamente cuando ingresen un PIN válido.
echo "[4/5] Aplicando reglas de intercepción de portal cautivo..."

# Permitir DNS (53), DHCP (67:68) y acceso local al Portal (8000)
iptables -C INPUT -i "$HOTSPOT_IFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$HOTSPOT_IFACE" -p udp --dport 53 -j ACCEPT
iptables -C INPUT -i "$HOTSPOT_IFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$HOTSPOT_IFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT
iptables -C INPUT -i "$HOTSPOT_IFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$HOTSPOT_IFACE" -p tcp --dport 8000 -j ACCEPT

# Redirigir puerto 80 al portal cautivo local
if ! iptables -t nat -C PREROUTING -i "$HOTSPOT_IFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null; then
  iptables -t nat -A PREROUTING -i "$HOTSPOT_IFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000
fi

# Bloquear tráfico de reenvío no autorizado por defecto
if ! iptables -C FORWARD -i "$HOTSPOT_IFACE" -j DROP 2>/dev/null; then
  iptables -A FORWARD -i "$HOTSPOT_IFACE" -j DROP
fi

# 5. Generar configuración Dnsmasq
echo "[5/5] Iniciando servidor DHCP y DNS Dnsmasq..."
sed \
  -e "s|__INTERFACE__|$HOTSPOT_IFACE|g" \
  -e "s|__HOST_IP__|$HOST_IP|g" \
  -e "s|__NETMASK__|$NETMASK|g" \
  -e "s|__DHCP_START__|$DHCP_START|g" \
  -e "s|__DHCP_END__|$DHCP_END|g" \
  "$TEMPLATE_FILE" > "$OUTPUT_CONF"

pkill -f "dnsmasq.*$OUTPUT_CONF" 2>/dev/null || true
dnsmasq -C "$OUTPUT_CONF" --pid-file=/run/ticketing_dnsmasq.pid

echo "=========================================================="
echo " [LISTO] Gateway Hotspot en Funcionamiento"
echo " Dispositivos en $HOTSPOT_IFACE serán interceptados."
echo " Solo navegarán en internet tras ingresar un PIN válido."
echo "=========================================================="
