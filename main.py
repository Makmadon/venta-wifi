import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.routers import captive, portal, admin_hotspot, catchall
from app.services import session_manager

async def session_expiration_watcher():
    """
    Background worker loop: checks active sessions every 5 seconds.
    When a user's prepaid time is up, immediately revokes their internet access!
    """
    while True:
        try:
            with SessionLocal() as db:
                session_manager.check_and_expire_sessions(db)
        except Exception:
            pass
        await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is created
    Base.metadata.create_all(bind=engine)
    # Start background session watcher
    watcher_task = asyncio.create_task(session_expiration_watcher())
    yield
    watcher_task.cancel()

app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema Autónomo de Venta de Acceso a Internet y Portal Cautivo Hotspot",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for local client isolation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")

# 1. Captive Network Assistant probes (Android, iOS, Windows)
app.include_router(captive.router)

# 2. Client Portal & Internet Access APIs
app.include_router(portal.router)

# 3. Admin Dashboard, POS & Voucher Generator
app.include_router(admin_hotspot.router)

# 4. Catch-all router for unmapped captive queries (MUST be registered last)
app.include_router(catchall.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
