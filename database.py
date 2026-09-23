"""
Database setup — SQLite via SQLAlchemy.
Swap SQLALCHEMY_DATABASE_URL for Postgres later without touching the rest of the app.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./source_registry.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed only for SQLite
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a session per request, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
