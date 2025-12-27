"""
JWT (JSON Web Token) authentication handler.

Supports:
- JWT token generation and validation
- Token refresh
- Claims extraction (user_id, tenant_id, roles)
"""
import logging
import time
from typing import Dict, List, Optional

import jwt
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class JWTConfig(BaseModel):
    """JWT configuration."""

    secret_key: str = Field(
        ...,
        description="Secret key for signing tokens (use strong random string in production)"
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration time in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration time in days"
    )
    issuer: str = Field(
        default="llm-app-saas",
        description="Token issuer"
    )
    audience: str = Field(
        default="llm-app-api",
        description="Token audience"
    )


class TokenClaims(BaseModel):
    """JWT token claims."""

    sub: str = Field(description="Subject (user_id)")
    tenant_id: str = Field(description="Tenant/organization ID")
    email: Optional[str] = Field(default=None, description="User email")
    roles: List[str] = Field(default_factory=list, description="User roles")
    permissions: List[str] = Field(default_factory=list, description="User permissions")

    # Standard JWT claims
    exp: int = Field(description="Expiration time (Unix timestamp)")
    iat: int = Field(description="Issued at (Unix timestamp)")
    iss: str = Field(description="Issuer")
    aud: str = Field(description="Audience")

    # Token type
    token_type: str = Field(default="access", description="Token type: access or refresh")


class JWTHandler:
    """Handle JWT token generation and validation."""

    def __init__(self, config: JWTConfig):
        """
        Initialize JWT handler.

        Args:
            config: JWT configuration
        """
        self.config = config

    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        email: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        extra_claims: Optional[Dict] = None
    ) -> str:
        """
        Create a JWT access token.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier
            email: User email
            roles: User roles (e.g., ["admin", "user"])
            permissions: User permissions (e.g., ["read:documents", "write:documents"])
            extra_claims: Additional custom claims

        Returns:
            Encoded JWT token string
        """
        now = int(time.time())
        exp = now + (self.config.access_token_expire_minutes * 60)

        claims = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "email": email,
            "roles": roles or [],
            "permissions": permissions or [],
            "exp": exp,
            "iat": now,
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "token_type": "access"
        }

        # Add extra claims
        if extra_claims:
            claims.update(extra_claims)

        token = jwt.encode(
            claims,
            self.config.secret_key,
            algorithm=self.config.algorithm
        )

        logger.info(
            f"Created access token for user={user_id}, tenant={tenant_id}, "
            f"expires_in={self.config.access_token_expire_minutes}m"
        )

        return token

    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str
    ) -> str:
        """
        Create a JWT refresh token.

        Refresh tokens have longer expiration and fewer claims.

        Args:
            user_id: User identifier
            tenant_id: Tenant identifier

        Returns:
            Encoded JWT refresh token
        """
        now = int(time.time())
        exp = now + (self.config.refresh_token_expire_days * 24 * 60 * 60)

        claims = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "exp": exp,
            "iat": now,
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "token_type": "refresh"
        }

        token = jwt.encode(
            claims,
            self.config.secret_key,
            algorithm=self.config.algorithm
        )

        logger.info(
            f"Created refresh token for user={user_id}, tenant={tenant_id}, "
            f"expires_in={self.config.refresh_token_expire_days}d"
        )

        return token

    def verify_token(self, token: str) -> TokenClaims:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token claims

        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                issuer=self.config.issuer
            )

            claims = TokenClaims(**payload)

            logger.debug(f"Token verified for user={claims.sub}, tenant={claims.tenant_id}")

            return claims

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise

        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            raise

    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Generate new access token from refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New access token

        Raises:
            ValueError: If refresh token is not of type 'refresh'
            jwt.InvalidTokenError: If token is invalid/expired
        """
        claims = self.verify_token(refresh_token)

        if claims.token_type != "refresh":
            raise ValueError("Token is not a refresh token")

        # Create new access token with same user/tenant
        new_access_token = self.create_access_token(
            user_id=claims.sub,
            tenant_id=claims.tenant_id,
            email=claims.email,
            roles=claims.roles,
            permissions=claims.permissions
        )

        logger.info(f"Refreshed access token for user={claims.sub}")

        return new_access_token

    def decode_token_without_verification(self, token: str) -> Dict:
        """
        Decode token without verifying signature (for debugging).

        WARNING: Do not use for authentication!

        Args:
            token: JWT token

        Returns:
            Decoded payload
        """
        return jwt.decode(token, options={"verify_signature": False})

    def has_role(self, token: str, required_role: str) -> bool:
        """
        Check if token has a specific role.

        Args:
            token: JWT token
            required_role: Role to check for

        Returns:
            True if user has the role
        """
        try:
            claims = self.verify_token(token)
            return required_role in claims.roles
        except jwt.InvalidTokenError:
            return False

    def has_permission(self, token: str, required_permission: str) -> bool:
        """
        Check if token has a specific permission.

        Args:
            token: JWT token
            required_permission: Permission to check for (e.g., "read:documents")

        Returns:
            True if user has the permission
        """
        try:
            claims = self.verify_token(token)
            return required_permission in claims.permissions
        except jwt.InvalidTokenError:
            return False


# Token extraction utilities
def extract_token_from_header(authorization_header: Optional[str]) -> Optional[str]:
    """
    Extract JWT token from Authorization header.

    Expected format: "Bearer <token>"

    Args:
        authorization_header: Authorization header value

    Returns:
        Extracted token or None
    """
    if not authorization_header:
        return None

    parts = authorization_header.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(f"Invalid Authorization header format: {authorization_header}")
        return None

    return parts[1]


def extract_token_from_cookie(cookies: Dict[str, str], cookie_name: str = "access_token") -> Optional[str]:
    """
    Extract JWT token from cookie.

    Args:
        cookies: Cookie dictionary
        cookie_name: Name of cookie containing token

    Returns:
        Token or None
    """
    return cookies.get(cookie_name)
