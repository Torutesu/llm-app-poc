"""
PostgreSQL-backed user management system.

Replaces in-memory storage with persistent database.
"""
import hashlib
import logging
import secrets
from datetime import datetime
from typing import List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import EmailStr

from auth.jwt_handler import JWTHandler
from auth.oauth_providers import OAuthUserInfo
from auth.user_manager import User

logger = logging.getLogger(__name__)


class PostgresUserManager:
    """User manager with PostgreSQL persistence."""

    def __init__(self, jwt_handler: JWTHandler, db_connection_string: str):
        """
        Initialize PostgreSQL user manager.

        Args:
            jwt_handler: JWT handler for token generation
            db_connection_string: PostgreSQL connection string
                Format: "postgresql://user:pass@host:port/dbname"
        """
        self.jwt_handler = jwt_handler
        self.db_connection_string = db_connection_string
        self.conn = None

    def connect(self):
        """Establish database connection."""
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                self.db_connection_string,
                cursor_factory=RealDictCursor
            )
            logger.info("Connected to PostgreSQL database")

    def close(self):
        """Close database connection."""
        if self.conn and not self.conn.closed:
            self.conn.close()
            logger.info("Closed PostgreSQL connection")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def create_user(
        self,
        email: EmailStr,
        tenant_id: str,
        password: Optional[str] = None,
        name: Optional[str] = None,
        roles: Optional[List[str]] = None
    ) -> User:
        """
        Create a new user.

        Args:
            email: User email
            tenant_id: Tenant ID
            password: Plain text password (will be hashed)
            name: User display name
            roles: User role names

        Returns:
            Created user

        Raises:
            ValueError: If user already exists
        """
        self.connect()

        # Check if user exists
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE tenant_id = %s AND email = %s",
                (tenant_id, email)
            )
            if cur.fetchone():
                raise ValueError(f"User with email {email} already exists in tenant {tenant_id}")

        # Generate user ID
        user_id = self._generate_user_id(email)

        # Hash password
        password_hash = None
        if password:
            password_hash = self._hash_password(password)

        # Insert user
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    user_id, tenant_id, email, name, password_hash,
                    is_active, is_verified, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id, tenant_id, email, name, password_hash,
                    True, False,  # is_active, is_verified
                    datetime.utcnow(), datetime.utcnow()
                )
            )

            # Assign roles
            if roles:
                for role_name in roles:
                    cur.execute(
                        """
                        INSERT INTO user_roles (user_id, role_id)
                        SELECT %s, role_id FROM roles WHERE role_name = %s
                        """,
                        (user_id, role_name)
                    )

            self.conn.commit()

        logger.info(f"Created user: {user_id} ({email}) in tenant {tenant_id}")

        return self.get_user(user_id)

    def create_oauth_user(
        self,
        oauth_info: OAuthUserInfo,
        tenant_id: str,
        roles: Optional[List[str]] = None
    ) -> User:
        """
        Create or update user from OAuth provider.

        Args:
            oauth_info: OAuth user information
            tenant_id: Tenant ID
            roles: User roles

        Returns:
            Created or existing user
        """
        self.connect()

        # Check if user exists by email
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE tenant_id = %s AND email = %s",
                (tenant_id, oauth_info.email)
            )
            existing = cur.fetchone()

            if existing:
                logger.info(f"OAuth user already exists: {existing['user_id']}")
                return self.get_user(existing['user_id'])

        # Generate user ID
        user_id = self._generate_user_id(oauth_info.email)

        # Insert user
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    user_id, tenant_id, email, name, given_name, family_name, picture,
                    oauth_provider, oauth_provider_user_id,
                    is_active, is_verified, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id, tenant_id, oauth_info.email,
                    oauth_info.name, oauth_info.given_name, oauth_info.family_name, oauth_info.picture,
                    oauth_info.provider, oauth_info.provider_user_id,
                    True, True,  # is_active, is_verified (OAuth users pre-verified)
                    datetime.utcnow(), datetime.utcnow()
                )
            )

            # Assign roles
            if roles:
                for role_name in roles:
                    cur.execute(
                        """
                        INSERT INTO user_roles (user_id, role_id)
                        SELECT %s, role_id FROM roles WHERE role_name = %s
                        """,
                        (user_id, role_name)
                    )

            self.conn.commit()

        logger.info(f"Created OAuth user: {user_id} via {oauth_info.provider}")

        return self.get_user(user_id)

    def authenticate_password(self, email: str, password: str, tenant_id: Optional[str] = None) -> Optional[User]:
        """
        Authenticate user with email/password.

        Args:
            email: User email
            password: Plain text password
            tenant_id: Optional tenant ID for filtering

        Returns:
            User if authenticated, None otherwise
        """
        self.connect()

        with self.conn.cursor() as cur:
            query = """
                SELECT user_id, password_hash, is_active
                FROM users
                WHERE email = %s
            """
            params = [email]

            if tenant_id:
                query += " AND tenant_id = %s"
                params.append(tenant_id)

            cur.execute(query, params)
            user_row = cur.fetchone()

            if not user_row:
                logger.warning(f"Authentication failed: user {email} not found")
                return None

            if not user_row['is_active']:
                logger.warning(f"User {email} is inactive")
                return None

            if not user_row['password_hash']:
                logger.warning(f"User {email} has no password (OAuth-only)")
                return None

            # Verify password
            if not self._verify_password(password, user_row['password_hash']):
                logger.warning(f"Authentication failed: invalid password for {email}")
                return None

            # Update last login
            cur.execute(
                "UPDATE users SET last_login_at = %s WHERE user_id = %s",
                (datetime.utcnow(), user_row['user_id'])
            )
            self.conn.commit()

        logger.info(f"User authenticated: {user_row['user_id']} ({email})")

        return self.get_user(user_row['user_id'])

    def get_user(self, user_id: str) -> Optional[User]:
        """
        Get user by ID with roles and permissions.

        Args:
            user_id: User identifier

        Returns:
            User object or None
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Get user
            cur.execute(
                """
                SELECT
                    user_id, tenant_id, email, name, given_name, family_name, picture,
                    password_hash, oauth_provider, oauth_provider_user_id,
                    is_active, is_verified, created_at, updated_at, last_login_at
                FROM users
                WHERE user_id = %s
                """,
                (user_id,)
            )
            user_row = cur.fetchone()

            if not user_row:
                return None

            # Get roles
            cur.execute(
                """
                SELECT r.role_name
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.role_id
                WHERE ur.user_id = %s
                """,
                (user_id,)
            )
            roles = [row['role_name'] for row in cur.fetchall()]

            # Get custom permissions
            cur.execute(
                """
                SELECT p.permission_name
                FROM user_custom_permissions ucp
                JOIN permissions p ON ucp.permission_id = p.permission_id
                WHERE ucp.user_id = %s
                """,
                (user_id,)
            )
            custom_permissions = [row['permission_name'] for row in cur.fetchall()]

        # Convert to User object
        user = User(
            user_id=user_row['user_id'],
            tenant_id=user_row['tenant_id'],
            email=user_row['email'],
            name=user_row['name'],
            given_name=user_row['given_name'],
            family_name=user_row['family_name'],
            picture=user_row['picture'],
            password_hash=user_row['password_hash'],
            oauth_provider=user_row['oauth_provider'],
            oauth_provider_user_id=user_row['oauth_provider_user_id'],
            roles=roles,
            custom_permissions=custom_permissions,
            is_active=user_row['is_active'],
            is_verified=user_row['is_verified'],
            created_at=user_row['created_at'].isoformat(),
            updated_at=user_row['updated_at'].isoformat(),
            last_login_at=user_row['last_login_at'].isoformat() if user_row['last_login_at'] else None
        )

        return user

    def get_user_by_email(self, email: str, tenant_id: str) -> Optional[User]:
        """Get user by email and tenant."""
        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE tenant_id = %s AND email = %s",
                (tenant_id, email)
            )
            row = cur.fetchone()

            if row:
                return self.get_user(row['user_id'])

        return None

    def update_user_roles(self, user_id: str, roles: List[str]) -> User:
        """
        Update user roles.

        Args:
            user_id: User identifier
            roles: New role names

        Returns:
            Updated user
        """
        self.connect()

        with self.conn.cursor() as cur:
            # Delete existing roles
            cur.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))

            # Insert new roles
            for role_name in roles:
                cur.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT %s, role_id FROM roles WHERE role_name = %s
                    """,
                    (user_id, role_name)
                )

            # Update updated_at
            cur.execute(
                "UPDATE users SET updated_at = %s WHERE user_id = %s",
                (datetime.utcnow(), user_id)
            )

            self.conn.commit()

        logger.info(f"Updated roles for user {user_id}: {roles}")

        return self.get_user(user_id)

    def add_permission(self, user_id: str, permission_name: str) -> User:
        """
        Add custom permission to user.

        Args:
            user_id: User identifier
            permission_name: Permission name

        Returns:
            Updated user
        """
        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_custom_permissions (user_id, permission_id)
                SELECT %s, permission_id FROM permissions WHERE permission_name = %s
                ON CONFLICT DO NOTHING
                """,
                (user_id, permission_name)
            )

            self.conn.commit()

        logger.info(f"Added permission {permission_name} to user {user_id}")

        return self.get_user(user_id)

    def create_tokens_for_user(self, user: User) -> dict:
        """
        Create JWT tokens for user.

        Args:
            user: User object

        Returns:
            Dictionary with access_token and refresh_token
        """
        access_token = self.jwt_handler.create_access_token(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            email=user.email,
            roles=user.roles,
            permissions=user.get_all_permissions()
        )

        refresh_token = self.jwt_handler.create_refresh_token(
            user_id=user.user_id,
            tenant_id=user.tenant_id
        )

        # Store refresh token in database
        self._store_refresh_token(user.user_id, user.tenant_id, refresh_token)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.jwt_handler.config.access_token_expire_minutes * 60
        }

    def _store_refresh_token(self, user_id: str, tenant_id: str, token: str):
        """Store refresh token in database."""
        self.connect()

        from datetime import timedelta

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(days=self.jwt_handler.config.refresh_token_expire_days)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO refresh_tokens (user_id, tenant_id, token_hash, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, tenant_id, token_hash, expires_at)
            )
            self.conn.commit()

    def list_users_by_tenant(self, tenant_id: str) -> List[User]:
        """List all users for a tenant."""
        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM users WHERE tenant_id = %s ORDER BY created_at DESC",
                (tenant_id,)
            )
            user_ids = [row['user_id'] for row in cur.fetchall()]

        return [self.get_user(uid) for uid in user_ids]

    def deactivate_user(self, user_id: str) -> User:
        """Deactivate user (soft delete)."""
        self.connect()

        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_active = FALSE, updated_at = %s WHERE user_id = %s",
                (datetime.utcnow(), user_id)
            )
            self.conn.commit()

        logger.info(f"Deactivated user {user_id}")

        return self.get_user(user_id)

    @staticmethod
    def _generate_user_id(email: str) -> str:
        """Generate user ID from email."""
        import uuid

        email_hash = hashlib.sha256(email.encode()).hexdigest()[:8]
        random_suffix = uuid.uuid4().hex[:8]

        return f"user_{email_hash}_{random_suffix}"

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password using PBKDF2-SHA256."""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )

        return f"pbkdf2_sha256$100000${salt}${pwd_hash.hex()}"

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        try:
            algorithm, iterations, salt, stored_hash = password_hash.split('$')

            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                int(iterations)
            )

            return pwd_hash.hex() == stored_hash

        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
