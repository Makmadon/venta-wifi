import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Local WiFi Ticketing & Captive Portal"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    HOST_IP: str = "192.168.4.1"
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/tickets.db"
    SECRET_KEY: str = "offline-secure-portal-key-2026-production"
    CURRENCY_SYMBOL: str = "$"
    BASE_URL: str = "http://192.168.4.1"
    
    # Static & Templates
    STATIC_DIR: str = str(BASE_DIR / "app" / "static")
    TEMPLATES_DIR: str = str(BASE_DIR / "app" / "templates")

settings = Settings()
