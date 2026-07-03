"""Database engine, session factory, and lifespan hooks."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import FastAPI, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.settings import get_settings


def create_db_connection(app: FastAPI) -> None:
    """Create engine + session factory and store them on app.state."""
    settings = get_settings()
    connect_args: dict = {}
    if settings.DB_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    eng = create_engine(settings.DB_URL, connect_args=connect_args)
    sf = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)

    app.state.engine = eng
    app.state.session_factory = sf

    from src.models.base import Base

    Base.metadata.create_all(bind=eng)
    run_startup_migrations(eng)


def run_startup_migrations(eng) -> None:
    """Additive column migrations (spec E.9).

    create_all() creates missing tables but never adds columns to existing
    ones. Compare live schema against the models and ALTER in the gaps —
    idempotent, additive-only (new columns are nullable or have a default).
    """
    from sqlalchemy import inspect, text

    from src.models.base import Base

    inspector = inspect(eng)
    with eng.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column.type.compile(eng.dialect)}"
                if column.default is not None and getattr(column.default, "arg", None) is not None:
                    arg = column.default.arg
                    if isinstance(arg, (int, float)):
                        ddl += f" DEFAULT {arg}"
                    elif isinstance(arg, str):
                        ddl += f" DEFAULT '{arg}'"
                conn.execute(text(ddl))


def shutdown_db_connection(app: FastAPI) -> None:
    """Dispose of the engine on shutdown."""
    app.state.engine.dispose()


def get_session(request: Request) -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session from the app-scoped factory."""
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
