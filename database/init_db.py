"""
Database initialization script.

Creates tables and optionally seeds initial data.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.connection import check_database_connection, create_tables, engine
from database.models import Base


def init_database():
    """Initialize database with tables."""
    print("Checking database connection...")

    if not check_database_connection():
        print("✗ Failed to connect to database")
        print(f"  Connection string: {engine.url}")
        print("\nMake sure PostgreSQL is running and the database exists.")
        print("To create database:")
        print("  createdb llm_app_auth")
        return False

    print("✓ Database connection successful")
    print("\nCreating tables...")

    try:
        create_tables()
        print("✓ Database tables created successfully")
        print("\nCreated tables:")
        for table in Base.metadata.sorted_tables:
            print(f"  - {table.name}")
        return True

    except Exception as e:
        print(f"✗ Failed to create tables: {e}")
        return False


def seed_test_data():
    """Seed database with test data."""
    from datetime import datetime

    from database.connection import get_db_context
    from database.models import UserModel

    print("\nSeeding test data...")

    try:
        with get_db_context() as db:
            # Check if data already exists
            existing = db.query(UserModel).first()
            if existing:
                print("  Database already has data, skipping seed")
                return

            # Create test users
            test_users = [
                {
                    "user_id": "user_admin_001",
                    "email": "admin@example.com",
                    "password_hash": "pbkdf2_sha256$100000$test$hashedpassword",  # Password: admin123
                    "name": "Admin User",
                    "tenant_id": "tenant_001",
                    "roles": ["admin"],
                    "is_active": True,
                    "is_verified": True,
                    "created_at": datetime.utcnow()
                },
                {
                    "user_id": "user_test_001",
                    "email": "user@example.com",
                    "password_hash": "pbkdf2_sha256$100000$test$hashedpassword",  # Password: user123
                    "name": "Test User",
                    "tenant_id": "tenant_001",
                    "roles": ["viewer"],
                    "is_active": True,
                    "is_verified": True,
                    "created_at": datetime.utcnow()
                }
            ]

            for user_data in test_users:
                user = UserModel(**user_data)
                db.add(user)

            db.commit()
            print(f"✓ Created {len(test_users)} test users")

    except Exception as e:
        print(f"✗ Failed to seed data: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize database")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed database with test data"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Database Initialization")
    print("=" * 60)

    success = init_database()

    if success and args.seed:
        seed_test_data()

    print("\n" + "=" * 60)
    if success:
        print("Database initialization complete!")
    else:
        print("Database initialization failed")
    print("=" * 60)
