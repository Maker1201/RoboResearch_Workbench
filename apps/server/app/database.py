from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def database_url() -> str:
    explicit = os.getenv("WORKBENCH_DATABASE_URL")
    if explicit:
        return explicit
    data_dir = project_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'workbench.db'}"


class Base(DeclarativeBase):
    pass


engine = create_engine(database_url(), connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

