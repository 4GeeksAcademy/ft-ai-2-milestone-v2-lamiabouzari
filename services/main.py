"""FastAPI application entry point."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the backend directory is on sys.path — uvicorn's reloader spawns
# subprocesses that don't always inherit the working directory, causing
# ``from config import ...`` and similar relative imports to fail.
_backend_dir = str(Path(__file__).resolve().parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
_repository_dir = str(Path(_backend_dir).parent)
if _repository_dir not in sys.path:
    sys.path.insert(0, _repository_dir)

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import backup_db, create_inventory_db_and_tables, get_db
from exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    request_validation_exception_handler,
)
from api.router import router as suppliers_router
from routers import agent, auth, chat, events, incidents, inventory, knowledge, profiles, rfp, tasks, telemetry, users
from reporting import router as reporting_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    # Startup: ensure the database is initialised
    get_db()
    # Insert the context suppliers when this process is a real server.
    # Tests set SUPPLIERS_SEED_ON_STARTUP=0 so they never write the live file.
    if os.getenv("SUPPLIERS_SEED_ON_STARTUP", "1") != "0":
        from api.seed import seed_suppliers

        seed_suppliers()
    # Inventory tables only apply when a Postgres DATABASE_URL is configured
    if settings.database_url:
        create_inventory_db_and_tables()
    yield
    # Shutdown: create a backup
    try:
        backup_db()
    except FileNotFoundError:
        pass  # No database file to back up yet


app = FastAPI(
    title="ft-ai-2-frontend-dev API",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Exception handlers — consistent error envelope
# ---------------------------------------------------------------------------

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
app.include_router(inventory.router)
app.include_router(telemetry.router)
app.include_router(reporting_router.router)
app.include_router(incidents.router)
app.include_router(tasks.router)
app.include_router(knowledge.router)
app.include_router(agent.router)
app.include_router(rfp.router)
app.include_router(events.router)
app.include_router(chat.router)
app.include_router(suppliers_router)

@app.get("/health")
def health_check() -> dict:
    """Simple health-check endpoint."""
    return {"status": "ok"}