import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routers import captive, events, tickets, admin, catchall

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is created
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous local ticketing POS and captive portal system",
    version="1.0.0",
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

# Jinja2 Templates
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)

# Root captive landing page
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse, tags=["Portal Home"])
def portal_home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"settings": settings}
    )

# 1. Captive Network Assistant probes (Android, iOS, Windows)
app.include_router(captive.router)

# 2. Public API routers
app.include_router(events.router)
app.include_router(tickets.router)

# 3. Admin & Gatekeeper verification
app.include_router(admin.router)

# 4. Catch-all router for unmapped captive queries (MUST be registered last)
app.include_router(catchall.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=False)
