# Guía Rápida de Uso y Reanudación (Quickstart)

Este documento te permite retomar el proyecto en cualquier momento sin perder tiempo en configuraciones.

---

## 1. Modos de Ejecución

Tienes dos formas de ejecutar el sistema: **Nativo en el Host** o **En Contenedor Docker**.

### Opción A: Modo Docker (Recomendado)
Ejecuta todo el sistema (DHCP, DNS Comodín, IPTables y Backend FastAPI) en un solo comando:

```bash
# 1. Asegúrate de que la interfaz en docker-compose.yml coincida con tu tarjeta Wi-Fi/Ethernet (ej: wlan0 o eth0)
# 2. Levantar el servicio
sudo docker compose up --build -d

# 3. Ver logs en tiempo real
sudo docker compose logs -f

# 4. Detener el servicio cuando termine el evento
sudo docker compose down
```

---

### Opción B: Modo Nativo en Linux

#### Paso 1: Configurar la Red del Portal Cautivo (Privilegios Root)
```bash
# Sintaxis: sudo ./scripts/setup_network.sh <interfaz> [ip_servidor]
sudo ./scripts/setup_network.sh wlan0 192.168.4.1
```

#### Paso 2: Iniciar el Servidor Web (Usuario Normal)
```bash
./scripts/run_portal.sh
```

#### Paso 3: Detener y Restaurar la Red al Finalizar
```bash
sudo ./scripts/teardown_network.sh wlan0 192.168.4.1
```

---

## 2. Enlaces y Accesos del Sistema

Una vez iniciado el servidor, se puede acceder desde cualquier dispositivo conectado:

* **Portal Cautivo de Clientes (Compra de Boletos):**
  * `http://192.168.4.1/` (o cualquier URL en el navegador del cliente gracias a la redirección comodín).
  * Permite ver eventos, elegir asientos o cantidad general, y generar el boleto digital con código QR.
* **Panel de Administración, Puerta y Taquilla POS:**
  * `http://192.168.4.1/admin`
  * **Pestaña 1 (Escáner QR):** Lee códigos con la cámara del celular/laptop o pistola USB para validar entradas y evitar doble ingreso.
  * **Pestaña 2 (Taquilla POS):** Venta rápida en efectivo a mano alzada.
  * **Pestaña 3 (Auditoría):** Listado y búsqueda de asistentes en tiempo real.
  * **Pestaña 4 (Crear Eventos):** Crear nuevos eventos con o sin numeración de asientos.
* **Documentación Interactiva Swagger / OpenAPI:**
  * `http://192.168.4.1:8000/docs`

---

## 3. Pruebas Automatizadas y Verificación de Concurrencia

Para verificar la integridad del sistema y la garantía de **cero sobreventa**:
```bash
PYTHONPATH=. ./venv/bin/pytest -v
```

---

## 4. Reinicio de Datos de Prueba (Base de Datos)

Si deseas limpiar o regenerar los eventos y boletos de demostración:
```bash
# Eliminar la base de datos actual
rm -f tickets.db tickets.db-wal tickets.db-shm data/tickets.db

# Repoblar con eventos de demostración
./venv/bin/python scripts/seed_data.py
```

---

## 5. Ubicación de Archivos Clave

| Componente | Ruta del Archivo |
| :--- | :--- |
| **Configuración** | [`app/config.py`](file:///home/stalinft/Documentos/venta-wifi/app/config.py) |
| **Modelos de Datos** | [`app/models.py`](file:///home/stalinft/Documentos/venta-wifi/app/models.py) |
| **Seguridad Criptográfica** | [`app/security.py`](file:///home/stalinft/Documentos/venta-wifi/app/security.py) |
| **Generador de QR** | [`app/qr_service.py`](file:///home/stalinft/Documentos/venta-wifi/app/qr_service.py) |
| **Sondas Portal Cautivo** | [`app/routers/captive.py`](file:///home/stalinft/Documentos/venta-wifi/app/routers/captive.py) |
| **Compra y Boletos** | [`app/routers/tickets.py`](file:///home/stalinft/Documentos/venta-wifi/app/routers/tickets.py) |
| **Administración & Puerta**| [`app/routers/admin.py`](file:///home/stalinft/Documentos/venta-wifi/app/routers/admin.py) |
| **Plantilla Dnsmasq** | [`network/dnsmasq.conf.template`](file:///home/stalinft/Documentos/venta-wifi/network/dnsmasq.conf.template) |
| **Scripts de Red** | [`scripts/setup_network.sh`](file:///home/stalinft/Documentos/venta-wifi/scripts/setup_network.sh) y [`scripts/teardown_network.sh`](file:///home/stalinft/Documentos/venta-wifi/scripts/teardown_network.sh) |
| **Docker Compose** | [`docker-compose.yml`](file:///home/stalinft/Documentos/venta-wifi/docker-compose.yml) y [`Dockerfile`](file:///home/stalinft/Documentos/venta-wifi/Dockerfile) |
| **Pruebas de Estrés** | [`tests/test_concurrency.py`](file:///home/stalinft/Documentos/venta-wifi/tests/test_concurrency.py) |
