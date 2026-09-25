FROM python:3.12-slim

# Prevent python from buffering stdout/stderr and writing .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL="sqlite:////app/data/tickets.db"

# Install network tools: dnsmasq, iptables, iproute2 (ip command), procps
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsmasq \
    iptables \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ app/
COPY network/ network/
COPY scripts/ scripts/
COPY main.py .
COPY docker/ docker/

# Ensure directory for persistent SQLite database
RUN mkdir -p /app/data && chmod +x docker/entrypoint.sh scripts/*.sh

# Ports:
# 53 (DNS UDP/TCP), 67 (DHCP UDP), 80 (HTTP captive), 8000 (Backend API)
EXPOSE 53/udp 53/tcp 67/udp 80 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
