"""Async SQLAlchemy engine / session management."""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


_is_sqlite = settings.database_url.startswith("sqlite")

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=not _is_sqlite,
    connect_args={"timeout": 30} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - driver hook
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()


SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


log = logging.getLogger("agentforge.db")


def _add_missing_columns(sync_conn) -> None:
    """Lightweight additive migration: add columns that exist in the models but not in the DB.

    Keeps existing local databases working after upgrades. (Use Alembic for anything
    beyond additive changes.)
    """
    insp = inspect(sync_conn)
    existing = set(insp.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            ddl = col.type.compile(dialect=sync_conn.dialect)
            default = ""
            sd = col.server_default
            if sd is not None and hasattr(sd, "arg"):
                arg = sd.arg
                if isinstance(arg, str):
                    default = " DEFAULT '" + arg.replace("'", "''") + "'"
                elif hasattr(arg, "text"):
                    default = f" DEFAULT {arg.text}"
            sync_conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}{default}'))
            log.info("migrated: added column %s.%s", table.name, col.name)


async def init_db() -> None:
    from app.modules import load_models

    load_models()  # register every module's tables

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
