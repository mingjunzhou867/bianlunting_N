"""Session resolution for Data Source Packs."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from config.settings import settings
from data_sources.loader import get_data_source_pack, resolve_data_source_id


class DataSourceSessionError(RuntimeError):
    """Raised when a data source cannot provide a runtime SQL session."""


_SESSION_FACTORIES: dict[str, sessionmaker] = {}


def _mysql_url_for_data_source(data_source_id: str) -> str:
    if data_source_id == "local_mysql_demo":
        return settings.local_mysql_demo_db_url
    if data_source_id == "sql_test_1000":
        return settings.sql_test_1000_db_url
    raise DataSourceSessionError(
        f"No MySQL connection settings registered for data source: {data_source_id}"
    )


def _session_factory_for_mysql_data_source(data_source_id: str) -> sessionmaker:
    url = _mysql_url_for_data_source(data_source_id)
    cached = _SESSION_FACTORIES.get(url)
    if cached is not None:
        return cached

    engine = create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False,
        connect_args={"charset": settings.local_mysql_demo_db_charset or settings.db_charset},
    )
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    _SESSION_FACTORIES[url] = factory
    return factory


@contextmanager
def get_session_for_data_source(data_source_id: str | None = None) -> Generator[Session, None, None]:
    """Resolve a data source pack to a SQLAlchemy session.

    MySQL business data sources use their own connection settings instead of
    the global system DB session. This keeps policy/history storage separate
    from pluggable business evidence retrieval.
    """
    resolved_id = resolve_data_source_id(data_source_id)
    pack = get_data_source_pack(resolved_id)
    if pack is None:
        raise DataSourceSessionError(f"Data source pack not found: {resolved_id}")

    source_type = pack.manifest.type.lower()
    connection_ref = pack.manifest.connection_ref.replace("\\", "/").lower()
    if source_type != "mysql":
        raise DataSourceSessionError(
            f"Data source type is not executable by SQLAlchemy MySQL session: {source_type}"
        )
    if connection_ref not in {
        "config/.env",
        "config.env",
        "config/.env:local_mysql_demo",
        "config/.env:sql_test_1000",
    }:
        raise DataSourceSessionError(
            f"Unsupported MySQL connection reference for {resolved_id}: {pack.manifest.connection_ref}"
        )

    factory = _session_factory_for_mysql_data_source(resolved_id)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
