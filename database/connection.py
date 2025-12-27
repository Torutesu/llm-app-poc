"""
Database connection and session management.

Provides SQLAlchemy engine and session factory.
"""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from database.models import Base

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/llm_app_auth"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connection before using
    echo=False,  # Set to True for SQL query logging
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def create_tables():
    """
    Create all tables in the database.

    Run this once to initialize the database schema.
    """
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")


def drop_tables():
    """
    Drop all tables in the database.

    WARNING: This will delete all data!
    """
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped")


def get_db() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.

    Usage in FastAPI:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            users = db.query(UserModel).all()
            return users

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Get database session as context manager.

    Usage:
        with get_db_context() as db:
            users = db.query(UserModel).all()

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test database connection
    if check_database_connection():
        print("✓ Database connection successful")

        # Create tables
        create_tables()
    else:
        print("✗ Database connection failed")
