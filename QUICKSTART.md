# Guía Rápida de Uso & Reanudación (Hotspot Billing Wi-Fi)

Esta guía te permite probar y operar el sistema de venta de tiempo de internet en segundos.

---

## 1. Modo Seguro de Prueba (Sin Desconectarte de tu Wi-Fi)

Para probar la venta de fichas, el portal cautivo con contador regresivo, el aviso de expiración y el generador de fichas sin afectar tu conexión a internet ni requerir root:

```bash
# 1. Iniciar el servidor localmente
./scripts/run_portal.sh

# 2. Acceder como Cliente (Portal de Entrada / Canje de PIN)
# Abre en tu navegador:
http://localhost:8000
# PINs precargados para probar: 123456 (1h), 654321 (1h), 777888 (3h)

# 3. Acceder como Dueño / Administrador
# Abre en tu navegador:
http://localhost:8000/admin
```

---

## 2. Modo Producción en Negocio (Gateway con Router Wi-Fi)

Cuando vayas a instalarlo en un router físico para clientes reales:

```bash
# 1. Configurar reglas de iptables y Dnsmasq (como root)
# Sintaxis: sudo ./scripts/setup_network.sh <interfaz_clientes> <interfaz_internet_wan> [ip_gateway]
sudo ./scripts/setup_network.sh wlan0 eth0 192.168.4.1

# 2. Iniciar el backend
./scripts/run_portal.sh

# 3. Detener y restaurar al finalizar
sudo ./scripts/teardown_network.sh wlan0 eth0 192.168.4.1
```

---

## 3. Modo Docker

```bash
# Iniciar con Docker Compose
sudo docker compose up --build -d

# Ver logs en vivo
sudo docker compose logs -f

# Detener el contenedor
sudo docker compose down
```

---

## 4. PINs y Fichas de Demostración para Pruebas

Al iniciar con la base de datos recién creada, tienes estos códigos listos:

| Código PIN | Plan de Tiempo | Duración | Precio |
| :---: | :---: | :---: | :---: |
| `123456` | 1 Hora de Conexión | 60 minutos | $0.50 |
| `654321` | 1 Hora de Conexión | 60 minutos | $0.50 |
| `777888` | 3 Horas Continuas | 180 minutos | $1.00 |
| `999000` | 1 Día Completo | 1440 minutos | $2.50 |

---

## 5. Impresión de Fichas Recortables de Bolsillo

1. Entra a `http://localhost:8000/admin`.
2. Ve a la pestaña **"Generador de Fichas (PINs)"**.
3. Selecciona el plan y la cantidad (ej: 20 fichas) y pulsa **"Generar Fichas Ahora"**.
4. Haz clic en **"🖨️ Abrir Plantilla de Impresión de Fichas"** (o entra directo a `http://localhost:8000/admin/vouchers/print`).
5. Imprime en cualquier impresora estándar y recorta las fichas con tijeras para vender en mostrador.

---

## 6. Pruebas Automatizadas

```bash
PYTHONPATH=. ./venv/bin/pytest -v
```
*(Valida las 12 pruebas de sondas Android/iOS/Windows, canje de PINs, recarga de tiempo y corte por expiración).*
