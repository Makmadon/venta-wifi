#!/usr/bin/env bash
# ==============================================================================
# Lanzador de Hotspot Dual (STA + AP Virtual Simultáneo)
# Emite Wi-Fi para clientes mientras la laptop sigue conectada a su Wi-Fi
# ==============================================================================
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "[ERROR] Este script debe ejecutarse como root (ej: sudo ./scripts/start_dual_hotspot.sh)"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

STA_IFACE="${1:-wlan0}"
AP_IFACE="ap0"
SSID="${2:-Internet_Fichas_Test}"
HOST_IP="192.168.4.1"

echo "=========================================================="
echo " Iniciando Modo Dual Virtual AP (Wi-Fi Repeater Hotspot)"
echo " Interfaz Wi-Fi Internet (STA) : $STA_IFACE"
echo " Interfaz Hotspot Virtual (AP) : $AP_IFACE"
echo " Nombre de Red a Emitir (SSID) : $SSID"
echo "=========================================================="

# 1. Comprobar si hostapd está instalado
if ! command -v hostapd > /dev/null 2>&1; then
  echo ""
  echo "[ERROR] 'hostapd' no está instalado en este sistema."
  echo "Para instalarlo:"
  echo "  • En Arch Linux / CachyOS : sudo pacman -S hostapd"
  echo "  • En Debian / Ubuntu / Pi : sudo apt install hostapd"
  echo ""
  exit 1
fi

# 2. Diagnóstico de canal actual de wlan0
echo "[1/6] Detectando frecuencia y canal de $STA_IFACE..."
FREQ_RAW=$(iw dev "$STA_IFACE" link 2>/dev/null | grep -i "freq:" | awk '{print $2}' || true)
FREQ=${FREQ_RAW%.*} # Quitar decimales si los hay

if [ -z "$FREQ" ]; then
  echo "[AVISO] No se detectó conexión activa en $STA_IFACE. Usando canal por defecto 6 (2437 MHz)."
  CHANNEL="6"
else
  if [ "$FREQ" -ge 2412 ] && [ "$FREQ" -le 2472 ]; then
    CHANNEL=$(( (FREQ - 2407) / 5 ))
  elif [ "$FREQ" -ge 5180 ] && [ "$FREQ" -le 5825 ]; then
    CHANNEL=$(( (FREQ - 5000) / 5 ))
  else
    CHANNEL="6"
  fi
  echo "Conectado en frecuencia $FREQ MHz -> Canal Wi-Fi: $CHANNEL"
fi

# 3. Crear interfaz virtual ap0 si no existe
echo "[2/6] Creando interfaz inalámbrica virtual $AP_IFACE sobre $STA_IFACE..."
if ip link show dev "$AP_IFACE" > /dev/null 2>&1; then
  echo "Interfaz $AP_IFACE ya existía. Reiniciando..."
  iw dev "$AP_IFACE" del 2>/dev/null || true
fi

iw dev "$STA_IFACE" interface add "$AP_IFACE" type __ap

# Evitar que NetworkManager interfiera con la interfaz virtual ap0
nmcli dev set "$AP_IFACE" managed no 2>/dev/null || true

# 4. Asignar IP al Hotspot Virtual
echo "[3/6] Asignando IP $HOST_IP/24 a $AP_IFACE..."
ip addr add "$HOST_IP/24" dev "$AP_IFACE"
ip link set dev "$AP_IFACE" up

# 5. Habilitar Reenvío e iptables entre ap0 y wlan0
echo "[4/6] Configurando reglas de firewall iptables..."
sysctl -w net.ipv4.ip_forward=1 > /dev/null

# NAT Masquerade de ap0 hacia wlan0
iptables -t nat -C POSTROUTING -o "$STA_IFACE" -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o "$STA_IFACE" -j MASQUERADE

# Redirigir puerto 80 al portal cautivo local
iptables -t nat -C PREROUTING -i "$AP_IFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000 2>/dev/null || iptables -t nat -A PREROUTING -i "$AP_IFACE" -p tcp --dport 80 -j REDIRECT --to-ports 8000

# Permitir DNS, DHCP y servidor local
iptables -C INPUT -i "$AP_IFACE" -p udp --dport 53 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$AP_IFACE" -p udp --dport 53 -j ACCEPT
iptables -C INPUT -i "$AP_IFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$AP_IFACE" -p udp --dport 67:68 --sport 67:68 -j ACCEPT
iptables -C INPUT -i "$AP_IFACE" -p tcp --dport 8000 -j ACCEPT 2>/dev/null || iptables -A INPUT -i "$AP_IFACE" -p tcp --dport 8000 -j ACCEPT

# Bloquear tráfico de reenvío no autorizado por defecto
iptables -C FORWARD -i "$AP_IFACE" -j DROP 2>/dev/null || iptables -A FORWARD -i "$AP_IFACE" -j DROP

# 6. Generar configuraciones para hostapd y dnsmasq
echo "[5/6] Iniciando hostapd y dnsmasq para $AP_IFACE..."
sed \
  -e "s|__AP_INTERFACE__|$AP_IFACE|g" \
  -e "s|__SSID__|$SSID|g" \
  -e "s|__CHANNEL__|$CHANNEL|g" \
  "$PROJECT_ROOT/network/hostapd.conf.template" > "$PROJECT_ROOT/network/hostapd.conf"

sed \
  -e "s|__INTERFACE__|$AP_IFACE|g" \
  -e "s|__HOST_IP__|$HOST_IP|g" \
  -e "s|__NETMASK__|255.255.255.0|g" \
  -e "s|__DHCP_START__|192.168.4.50|g" \
  -e "s|__DHCP_END__|192.168.4.200|g" \
  "$PROJECT_ROOT/network/dnsmasq.conf.template" > "$PROJECT_ROOT/network/dnsmasq_dual.conf"

# Detener instancias previas si las hay
pkill -f "hostapd.*network/hostapd.conf" 2>/dev/null || true
pkill -f "dnsmasq.*network/dnsmasq_dual.conf" 2>/dev/null || true

# Iniciar servicios
hostapd -B "$PROJECT_ROOT/network/hostapd.conf"
dnsmasq -C "$PROJECT_ROOT/network/dnsmasq_dual.conf" --pid-file=/run/hotspot_dual_dnsmasq.pid

echo "=========================================================="
echo " [¡HOTSPOT DUAL ACTIVO CON ÉXITO!]"
echo " • Red Wi-Fi Emitida : $SSID"
echo " • Canal             : $CHANNEL (Sincronizado con $STA_IFACE)"
echo " • Tu Laptop Sigue   : Conectada a tu Wi-Fi e Internet normal"
echo " • Conecta tu celular a la red '$SSID' para probar el corte"
echo "=========================================================="
echo "Iniciando servidor de Venta de Internet en el puerto 8000..."
echo "Presiona Ctrl+C para detener."

cleanup() {
  echo ""
  echo "Deteniendo Hotspot y limpiando interfaz virtual..."
  "$PROJECT_ROOT/scripts/stop_dual_hotspot.sh" "$STA_IFACE"
  exit 0
}
trap cleanup SIGINT SIGTERM

# Iniciar servidor FastAPI
if [ -f "$PROJECT_ROOT/venv/bin/python" ]; then
  PYTHON="$PROJECT_ROOT/venv/bin/python"
  UVICORN="$PROJECT_ROOT/venv/bin/uvicorn"
else
  PYTHON="python3"
  UVICORN="uvicorn"
fi

$PYTHON "$PROJECT_ROOT/scripts/seed_data.py"
exec $UVICORN main:app --host 0.0.0.0 --port 8000
