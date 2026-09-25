# Guía de Compatibilidad de Dispositivos (Laptops, Raspberry Pi) y Despliegue en Docker

Esta guía explica cómo ejecutar el sistema de venta de tiempo de internet en diferentes tipos de hardware (tu laptop actual, Raspberry Pi 3/4/5, Mini PCs) y cómo desplegarlo con Docker.

---

## 1. Verificación Automática de Hardware

El proyecto incluye un script de diagnóstico que analiza el modelo de tu dispositivo y las capacidades de tu controlador inalámbrico en el kernel de Linux:

```bash
./scripts/check_hardware.sh
```

### ¿Qué analiza el script?
1. **Modelo del dispositivo:** Detecta si es una Laptop, PC de escritorio o una placa **Raspberry Pi** (3, 4, 5).
2. **Soporte de Modo AP (Access Point):** Confirma si tu tarjeta Wi-Fi puede emitir señal.
3. **Soporte de Modo Dual (STA + AP Simultáneos):** Determina si la tarjeta puede emitir el Hotspot para clientes mientras permanece conectada a tu Wi-Fi de internet en el mismo canal de radiofrecuencia.
4. **Recomendación de arquitectura:** Indica el modo óptimo para tu hardware específico.

---

## 2. Escenario A: Tu Laptop Actual (Modo Dual Virtual AP)

Tu laptop cuenta con una tarjeta **Intel Wi-Fi 6 AX201**. Esta tarjeta soporta la combinación:
`#{ managed } <= 1, #{ AP } <= 1, #channels <= 1`

Esto significa que **puede recibir internet por Wi-Fi (`wlan0`) y emitir el Hotspot (`ap0`) simultáneamente sin desconectarse de tu red.**

### Requisito previo (Solo la primera vez)
Instalar el emisor de Wi-Fi `hostapd`:
* En CachyOS / Arch Linux:
  ```bash
  sudo pacman -S hostapd
  ```
* En Ubuntu / Debian:
  ```bash
  sudo apt install hostapd
  ```

### Puesta en Marcha del Hotspot Dual
Ejecuta el script automatizado:
```bash
sudo ./scripts/start_dual_hotspot.sh wlan0 Internet_Fichas_Test
```

**Lo que hace el script automáticamente:**
1. Detecta en qué canal está tu Wi-Fi de casa (ej. Canal 6).
2. Crea una interfaz inalámbrica virtual secundaria llamada `ap0`.
3. Sincroniza `hostapd` para emitir la red `Internet_Fichas_Test` en el mismo canal.
4. Configura el servidor DHCP `dnsmasq` y las reglas de `iptables` en `ap0`.
5. Inicia el servidor web en el puerto 8000.
6. **Tu laptop sigue con internet normal**, mientras que cualquier celular conectado a `Internet_Fichas_Test` queda atrapado en el portal cautivo hasta que ingrese un PIN.

### Detener el Hotspot y Limpiar la Interfaz Virtual
Al pulsar `Ctrl+C` en la terminal (o ejecutando):
```bash
sudo ./scripts/stop_dual_hotspot.sh wlan0
```
La interfaz virtual `ap0` se elimina y las reglas de red se restauran de inmediato.

---

## 3. Escenario B: En Raspberry Pi (3B+, 4B, 5)

La Raspberry Pi es uno de los dispositivos más populares y económicos para dejar este sistema funcionando 24/7 en un local comercial.

### Arquitectura Recomendada en Raspberry Pi:
El chip Wi-Fi integrado Broadcom de la Raspberry Pi soporta modo AP, pero para garantizar máxima estabilidad y velocidad para muchos usuarios conectados, **la mejor práctica en una Raspberry Pi es:**

* **Internet de entrada (WAN):** Cable Ethernet `eth0` conectado al módem de la compañía telefónica.
* **Wi-Fi de salida para clientes (Hotspot LAN):** La tarjeta inalámbrica integrada `wlan0`.

```
[ Módem de Internet ]
        │ (Cable de red Ethernet)
        ▼
[ Puerto eth0 de la Raspberry Pi ]
        │
        ├── Servidor Hotspot (Control de tiempo + iptables)
        │
        ▼ (Señal Wi-Fi emitida por wlan0)
[ Celulares de los Clientes ]
```

### Puesta en Marcha en Raspberry Pi (Raspberry Pi OS / Debian):
```bash
# 1. Clonar el repositorio
git clone https://github.com/Makmadon/venta-wifi.git
cd venta-wifi

# 2. Instalar herramientas
sudo apt update
sudo apt install -y python3-venv dnsmasq iptables

# 3. Configurar entorno virtual
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 4. Iniciar el Gateway Hotspot (wlan0 clientes, eth0 internet)
sudo ./scripts/setup_network.sh wlan0 eth0 192.168.4.1

# 5. Iniciar la aplicación
./scripts/run_portal.sh
```

*(Opcional: Si deseas que la Raspberry Pi no use cable Ethernet y reciba internet por Wi-Fi, solo necesitas conectarle una antena Wi-Fi USB de $5 para tener dos interfaces Wi-Fi independientes: `wlan0` para recibir y `wlan1` para emitir).*

---

## 4. Escenario C: Despliegue con Docker (PC o Raspberry Pi)

Puedes empaquetar y levantar todo el sistema con **Docker Compose**.

### Estructura de `docker-compose.yml`
```yaml
services:
  hotspot-billing:
    build: .
    container_name: wifi-hotspot-portal
    restart: unless-stopped
    network_mode: "host"       # Indispensable para DHCP broadcast y DNS
    cap_add:
      - NET_ADMIN              # Indispensable para iptables y control de tráfico
      - NET_RAW
    environment:
      - WAN_INTERFACE=eth0     # Interfaz con Internet
      - HOTSPOT_INTERFACE=wlan0# Interfaz para los clientes
      - HOST_IP=192.168.4.1
      - ENABLE_NETWORK_SETUP=true
    volumes:
      - ./data:/app/data       # Base de datos SQLite persistente
```

### Comandos de Docker:
```bash
# Construir e iniciar
sudo docker compose up --build -d

# Ver registros en tiempo real
sudo docker compose logs -f

# Detener el contenedor
sudo docker compose down
```

---

## 5. Tabla Resumen de Métodos por Dispositivo

| Dispositivo | Entrada de Internet (WAN) | Emisión Hotspot (LAN) | Comando / Método Recomendado |
| :--- | :--- | :--- | :--- |
| **Laptop Intel AX201 (Tu PC)** | Wi-Fi (`wlan0`) | Virtual AP (`ap0`) | `sudo ./scripts/start_dual_hotspot.sh wlan0` |
| **Raspberry Pi 3/4/5** | Cable Ethernet (`eth0`) | Wi-Fi integrado (`wlan0`) | `sudo ./scripts/setup_network.sh wlan0 eth0 192.168.4.1` |
| **PC con 2 antenas Wi-Fi** | Wi-Fi 1 (`wlan0`) | Wi-Fi 2 (`wlan1`) | `sudo ./scripts/setup_network.sh wlan1 wlan0 192.168.4.1` |
| **Cualquier PC (Modo Router)** | Cable Ethernet (`eth0`) | Router Wi-Fi por cable LAN | `sudo ./scripts/setup_network.sh eth1 eth0 192.168.4.1` |
| **Cualquier PC en Docker** | Según variables en `.env` | Según variables en `.env` | `sudo docker compose up -d` |
