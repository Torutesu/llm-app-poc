"""
User management system.

Handles:
- User creation and authentication
- Password hashing
- OAuth user linking
- Role and permission management
"""
import hashlib
import logging
import secrets
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field

from auth.auth_middleware import ROLE_PERMISSIONS, get_permissions_for_roles
from auth.jwt_handler import JWTHandler
from auth.oauth_providers import OAuthUserInfo
from auth.password_reset import PasswordResetManager

logger = logging.getLogger(__name__)


class User(BaseModel):
    """User model."""

    user_id: str = Field(description="Unique user identifier")
    tenant_id: str = Field(description="Tenant this user belongs to")
    email: EmailStr = Field(description="User email")

    # Profile
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None

    # Authentication
    password_hash: Optional[str] = Field(
        default=None,
        description="Hashed password (null for OAuth-only users)"
    )
    oauth_provider: Optional[str] = Field(
        default=None,
        description="OAuth provider (google, microsoft, etc.)"
    )
    oauth_provider_user_id: Optional[str] = Field(
        default=None,
        description="User ID from OAuth provider"
    )

    # Authorization
    roles: List[str] = Field(default_factory=list, description="User roles")
    custom_permissions: List[str] = Field(
        default_factory=list,
        description="Additional permissions beyond role defaults"
    )

    # Status
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_login_at: Optional[str] = None

    def get_all_permissions(self) -> List[str]:
        """Get all permissions (from roles + custom)."""
        role_perms = get_permissions_for_roles(self.roles)
        all_perms = set(role_perms) | set(self.custom_permissions)
        return list(all_perms)


class UserManager:
    """Manage users and authentication."""

    def __init__(
        self,
        jwt_handler: JWTHandler,
        password_reset_manager: Optional[PasswordResetManager] = None
    ):
        """
        Initialize user manager.

        Args:
            jwt_handler: JWT handler for creating tokens
            password_reset_manager: Password reset manager (optional)
        """
        self.jwt_handler = jwt_handler
        self.password_reset_manager = password_reset_manager or PasswordResetManager()

        # In-memory user storage (in production: use PostgreSQL)
        self._users: Dict[str, User] = {}
        self._email_to_user_id: Dict[str, str] = {}

    def create_user(
        self,
        email: str,
        tenant_id: str,
        password: Optional[str] = None,
        name: Optional[str] = None,
        roles: Optional[List[str]] = None
    ) -> User:
        """
        Create a new user with password authentication.

        Args:
            email: User email
            tenant_id: Tenant ID
            password: Plain text password (will be hashed)
            name: User display name
            roles: User roles

        Returns:
            Created user

        Raises:
            ValueError: If user already exists
        """
        # Check if user exists
        if email in self._email_to_user_id:
            raise ValueError(f"User with email {email} already exists")

        # Generate user ID
        user_id = self._generate_user_id(email)

        # Hash password
        password_hash = None
        if password:
            password_hash = self._hash_password(password)

        # Create user
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            name=name,
            password_hash=password_hash,
            roles=roles or ["viewer"],  # Default role
            is_verified=False
        )

        # Store user
        self._users[user_id] = user
        self._email_to_user_id[email] = user_id

        logger.info(f"Created user: {user_id} ({email}) for tenant {tenant_id}")

        return user

    def create_oauth_user(
        self,
        oauth_info: OAuthUserInfo,
        tenant_id: str,
        roles: Optional[List[str]] = None
    ) -> User:
        """
        Create user from OAuth provider info.

        Args:
            oauth_info: OAuth user information
            tenant_id: Tenant ID to assign
            roles: User roles

        Returns:
            Created or existing user
        """
        # Check if user already exists
        existing_user_id = self._email_to_user_id.get(oauth_info.email)

        if existing_user_id:
            user = self._users[existing_user_id]
            logger.info(f"OAuth user already exists: {user.user_id}")
            return user

        # Generate user ID
        user_id = self._generate_user_id(oauth_info.email)

        # Create user
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email=oauth_info.email,
            name=oauth_info.name,
            given_name=oauth_info.given_name,
            family_name=oauth_info.family_name,
            picture=oauth_info.picture,
            oauth_provider=oauth_info.provider,
            oauth_provider_user_id=oauth_info.provider_user_id,
            roles=roles or ["viewer"],
            is_verified=True  # OAuth users are pre-verified
        )

        # Store user
        self._users[user_id] = user
        self._email_to_user_id[oauth_info.email] = user_id

        logger.info(
            f"Created OAuth user: {user_id} ({oauth_info.email}) "
            f"via {oauth_info.provider}"
        )

        return user

    def authenticate_password(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with email/password.

        Args:
            email: User email
            password: Plain text password

        Returns:
            User if authenticated, None otherwise
        """
        user_id = self._email_to_user_id.get(email)

        if not user_id:
            logger.warning(f"Authentication failed: user {email} not found")
            return None

        user = self._users[user_id]

        if not user.password_hash:
            logger.warning(f"User {email} has no password (OAuth-only)")
            return None

        if not user.is_active:
            logger.warning(f"User {email} is inactive")
            return None

        # Verify password
        if not self._verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: invalid password for {email}")
            return None

        # Update last login
        user.last_login_at = datetime.utcnow().isoformat()

        logger.info(f"User authenticated: {user_id} ({email})")

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        user_id = self._email_to_user_id.get(email)
        if user_id:
            return self._users[user_id]
        return None

    def update_user_roles(self, user_id: str, roles: List[str]) -> User:
        """
        Update user roles.

        Args:
            user_id: User identifier
            roles: New roles

        Returns:
            Updated user

        Raises:
            ValueError: If user not found
        """
        user = self._users.get(user_id)

        if not user:
            raise ValueError(f"User {user_id} not found")

        user.roles = roles
        user.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Updated roles for user {user_id}: {roles}")

        return user

    def add_permission(self, user_id: str, permission: str) -> User:
        """
        Add custom permission to user.

        Args:
            user_id: User identifier
            permission: Permission to add

        Returns:
            Updated user
        """
        user = self._users.get(user_id)

        if not user:
            raise ValueError(f"User {user_id} not found")

        if permission not in user.custom_permissions:
            user.custom_permissions.append(permission)
            user.updated_at = datetime.utcnow().isoformat()

            logger.info(f"Added permission {permission} to user {user_id}")

        return user

    def create_tokens_for_user(self, user: User) -> Dict[str, str]:
        """
        Create JWT access and refresh tokens for user.

        Args:
            user: User to create tokens for

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

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.jwt_handler.config.access_token_expire_minutes * 60
        }

    def list_users_by_tenant(self, tenant_id: str) -> List[User]:
        """
        List all users for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of users
        """
        return [u for u in self._users.values() if u.tenant_id == tenant_id]

    def deactivate_user(self, user_id: str) -> User:
        """
        Deactivate user (soft delete).

        Args:
            user_id: User to deactivate

        Returns:
            Updated user
        """
        user = self._users.get(user_id)

        if not user:
            raise ValueError(f"User {user_id} not found")

        user.is_active = False
        user.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Deactivated user {user_id}")

        return user

    def request_password_reset(self, email: str) -> bool:
        """
        Request password reset for user.

        Args:
            email: User email

        Returns:
            True if reset email sent
        """
        user = self.get_user_by_email(email)

        if not user:
            # Return True even if user not found (security: don't reveal user existence)
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return True

        return self.password_reset_manager.request_password_reset(
            user_id=user.user_id,
            email=user.email
        )

    def reset_password_with_token(self, token: str, new_password: str) -> bool:
        """
        Reset user password using reset token.

        Args:
            token: Password reset token
            new_password: New password

        Returns:
            True if password reset successfully
        """
        user_id = self.password_reset_manager.reset_password(
            token=token,
            new_password=new_password,
            password_hash_func=self._hash_password
        )

        if not user_id:
            return False

        # Update user password
        user = self._users.get(user_id)

        if not user:
            logger.error(f"User {user_id} not found during password reset")
            return False

        user.password_hash = self._hash_password(new_password)
        user.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Password reset completed for user {user_id}")

        return True

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """
        Change user password (requires old password verification).

        Args:
            user_id: User identifier
            old_password: Current password
            new_password: New password

        Returns:
            True if password changed successfully
        """
        user = self._users.get(user_id)

        if not user:
            raise ValueError(f"User {user_id} not found")

        if not user.password_hash:
            raise ValueError(f"User {user_id} is OAuth-only (no password)")

        # Verify old password
        if not self._verify_password(old_password, user.password_hash):
            logger.warning(f"Invalid old password for user {user_id}")
            return False

        # Update password
        user.password_hash = self._hash_password(new_password)
        user.updated_at = datetime.utcnow().isoformat()

        logger.info(f"Password changed for user {user_id}")

        return True

    @staticmethod
    def _generate_user_id(email: str) -> str:
        """Generate user ID from email."""
        import uuid

        # Create deterministic ID based on email
        email_hash = hashlib.sha256(email.encode()).hexdigest()[:8]
        random_suffix = uuid.uuid4().hex[:8]

        return f"user_{email_hash}_{random_suffix}"

    @staticmethod
    def _hash_password(password: str) -> str:
        """
        Hash password using PBKDF2-SHA256.

        Args:
            password: Plain text password

        Returns:
            Hashed password with salt
        """
        import hashlib

        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000  # iterations
        )

        # Format: algorithm$iterations$salt$hash
        return f"pbkdf2_sha256$100000${salt}${pwd_hash.hex()}"

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password to verify
            password_hash: Stored password hash

        Returns:
            True if password matches
        """
        import hashlib

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
