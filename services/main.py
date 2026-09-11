"""FastAPI application entry point."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the backend directory is on sys.path — uvicorn's reloader spawns
# subprocesses that don't always inherit the working directory, causing
# ``from config import ...`` and similar relative imports to fail.
_backend_dir = str(Path(__file__).resolve().parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

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
from routers import auth, inventory, profiles, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    # Startup: ensure the database is initialised
    get_db()
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

@app.get("/health")
def health_check() -> dict:
    """Simple health-check endpoint."""
    return {"status": "ok"}