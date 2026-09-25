import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "WiFi Hotspot & Control de Acceso a Internet"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Network Interfaces
    WAN_INTERFACE: str = "eth0"         # Interfaz con salida a internet
    HOTSPOT_INTERFACE: str = "wlan0"    # Interfaz donde se conectan los clientes
    HOST_IP: str = "192.168.4.1"        # IP Gateway del Hotspot
    BASE_URL: str = "http://192.168.4.1"
    
    # Database & Storage
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/tickets.db"
    SECRET_KEY: str = "offline-secure-portal-key-2026-production"
    CURRENCY_SYMBOL: str = "$"
    
    # Hotspot Rules
    FREE_TRIAL_ENABLED: bool = True
    FREE_TRIAL_MINUTES: int = 5
    FIREWALL_MODE: str = "auto"         # 'iptables', 'simulated', o 'auto'
    
    # Directories
    STATIC_DIR: str = str(BASE_DIR / "app" / "static")
    TEMPLATES_DIR: str = str(BASE_DIR / "app" / "templates")

settings = Settings()
