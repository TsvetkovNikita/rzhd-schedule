from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.config import cfg
from db.models import Base
from db.repositories import RepositoryHub

engine = create_engine(
    cfg.database_url,
    echo=cfg.db_echo,
    future=True,
    pool_pre_ping=cfg.db_pool_pre_ping,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
    expire_on_commit=False,
)


class RepositoryGateway:
    """Единая точка входа в слой репозиториев."""

    @contextmanager
    def session_scope(self) -> Iterator[RepositoryHub]:
        session = SessionLocal()
        try:
            yield RepositoryHub(session)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_schema(self) -> None:
        Base.metadata.create_all(bind=engine)

    def ping(self) -> bool:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return True


repository_gateway = RepositoryGateway()


def init_database() -> None:
    if cfg.db_auto_create:
        repository_gateway.create_schema()
