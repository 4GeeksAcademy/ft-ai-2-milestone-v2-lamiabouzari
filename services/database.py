"""TinyDB initialization and Pydantic middleware setup."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB
from tinydb.table import Document

from config import settings


class PydanticMiddleware:
    """A TinyDB middleware that bridges Pydantic models and TinyDB documents.

    Handles automatic serialisation of complex types (UUIDs, datetimes) and
    deserialisation back to Pydantic models on read.
    """

    def __init__(self, model_cls: type[BaseModel]) -> None:
        self._model_cls = model_cls

    def serialize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Serialize a dict to a storage-safe format."""
        return _encode_values(data)

    def deserialize(self, doc: Document) -> BaseModel:
        """Deserialize a TinyDB document back into a Pydantic model."""
        decoded = _decode_values(dict(doc))
        return self._model_cls.model_validate(decoded)


# ---------------------------------------------------------------------------
# Encoding / decoding helpers
# ---------------------------------------------------------------------------


def _encode_values(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively encode non-JSON-serialisable values."""
    encoded: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, uuid.UUID):
            encoded[key] = {"__type__": "uuid", "value": str(value)}
        elif isinstance(value, datetime):
            encoded[key] = {"__type__": "datetime", "value": value.isoformat()}
        elif isinstance(value, BaseModel):
            encoded[key] = _encode_values(value.model_dump())
        elif isinstance(value, dict):
            encoded[key] = _encode_values(value)
        elif isinstance(value, list):
            encoded[key] = [
                _encode_values(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            encoded[key] = value
    return encoded


def _decode_values(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively decode type-tagged values back to native Python objects."""
    decoded: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict) and "__type__" in value:
            decoded[key] = _decode_tagged(value)
        elif isinstance(value, dict):
            decoded[key] = _decode_values(value)
        elif isinstance(value, list):
            decoded[key] = [
                _decode_values(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            decoded[key] = value
    return decoded


def _decode_tagged(tagged: dict[str, str]) -> Any:
    """Decode a single type-tagged value."""
    tag = tagged["__type__"]
    raw = tagged["value"]
    if tag == "uuid":
        return uuid.UUID(raw)
    if tag == "datetime":
        return datetime.fromisoformat(raw)
    return raw


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class _CustomJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles our tagged types."""

    def default(self, o: Any) -> Any:
        if isinstance(o, uuid.UUID):
            return {"__type__": "uuid", "value": str(o)}
        if isinstance(o, datetime):
            return {"__type__": "datetime", "value": o.isoformat()}
        return super().default(o)


def _custom_json_decoder(d: dict[str, Any]) -> dict[str, Any]:
    """JSON object hook — passes through so TinyDB handles it."""
    return d


def _create_storage(db_path: str) -> TinyDB:
    """Create a TinyDB instance with custom JSON encoder/decoder."""
    from tinydb.storages import JSONStorage

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    return TinyDB(
        db_path,
        storage=JSONStorage,
        cls=_CustomJSONEncoder,
    )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_db: TinyDB | None = None


def get_db() -> TinyDB:
    """Return the application-wide TinyDB instance (create on first call)."""
    global _db
    if _db is None:
        _db = _create_storage(settings.database_path)
    return _db


def backup_db() -> Path:
    """Create a timestamped copy of the database file."""
    from shutil import copy2

    src = Path(settings.database_path)
    if not src.exists():
        raise FileNotFoundError(f"Database file not found: {src}")

    backups_dir = Path("backups")
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dst = backups_dir / f"db_backup_{timestamp}.json"
    copy2(src, dst)
    return dst


# ---------------------------------------------------------------------------
# Inventory database (Postgres via SQLModel) — separate from the TinyDB
# user/auth database above. Names are prefixed with ``inventory_`` to avoid
# any collision with the TinyDB helpers (``get_db``/``backup_db``).
# ---------------------------------------------------------------------------

_inventory_engine = None


def get_inventory_engine():
    """Return the singleton SQLAlchemy engine for the inventory database."""
    global _inventory_engine
    if _inventory_engine is None:
        if not settings.database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured; inventory endpoints require "
                "a Postgres connection string."
            )
        # ``prepare_threshold`` is a psycopg (PostgreSQL) driver option and is
        # invalid for SQLite/other drivers, so only pass it for Postgres URLs.
        connect_args = (
            {"prepare_threshold": None}
            if settings.database_url.startswith("postgresql")
            else {}
        )
        _inventory_engine = create_engine(
            settings.database_url,
            echo=False,
            poolclass=NullPool,
            connect_args=connect_args,
        )
    return _inventory_engine


def create_inventory_db_and_tables() -> None:
    """Create the relational inventory and telemetry tables when absent."""
    from models.inventory import SKU, StockEntry, StockExit  # noqa: F401
    from models.telemetry import TelemetryEventRecord  # noqa: F401

    SQLModel.metadata.create_all(get_inventory_engine())


def get_inventory_db():
    """Yield a SQLModel session for one FastAPI request (inventory only)."""
    with Session(get_inventory_engine()) as session:
        yield session