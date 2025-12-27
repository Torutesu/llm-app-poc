"""
Authentication middleware for API requests.

Integrates with:
- JWT token validation
- Tenant context
- Role-based access control (RBAC)
- Permission checking
"""
import logging
from typing import Callable, Dict, List, Optional

import jwt

from auth.jwt_handler import JWTHandler, extract_token_from_header
from middleware.tenant_context import TenantContext

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when user lacks required permissions."""
    pass


class AuthMiddleware:
    """Authentication and authorization middleware."""

    def __init__(self, jwt_handler: JWTHandler, require_auth: bool = True):
        """
        Initialize auth middleware.

        Args:
            jwt_handler: JWT handler instance
            require_auth: If True, reject requests without valid token
        """
        self.jwt_handler = jwt_handler
        self.require_auth = require_auth

    def authenticate_request(self, request_data: Dict) -> Dict:
        """
        Authenticate incoming request using JWT token.

        Args:
            request_data: Request data including headers

        Returns:
            Enriched request data with user/tenant context

        Raises:
            AuthenticationError: If authentication fails
        """
        # Extract token from Authorization header
        headers = request_data.get("headers", {})
        auth_header = headers.get("authorization") or headers.get("Authorization")

        token = extract_token_from_header(auth_header)

        if not token:
            if self.require_auth:
                raise AuthenticationError("Missing authentication token")
            else:
                logger.warning("No authentication token provided")
                return request_data

        # Verify token
        try:
            claims = self.jwt_handler.verify_token(token)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")

        # Set tenant and user context
        TenantContext.set_tenant(claims.tenant_id)
        TenantContext.set_user(claims.sub)

        # Add claims to request data
        request_data["authenticated"] = True
        request_data["user_id"] = claims.sub
        request_data["tenant_id"] = claims.tenant_id
        request_data["user_email"] = claims.email
        request_data["user_roles"] = claims.roles
        request_data["user_permissions"] = claims.permissions
        request_data["jwt_claims"] = claims

        logger.info(
            f"Authenticated request: user={claims.sub}, tenant={claims.tenant_id}, "
            f"roles={claims.roles}"
        )

        return request_data

    def require_role(self, request_data: Dict, required_role: str) -> None:
        """
        Check if user has required role.

        Args:
            request_data: Authenticated request data
            required_role: Required role name

        Raises:
            AuthorizationError: If user lacks the role
        """
        user_roles = request_data.get("user_roles", [])

        if required_role not in user_roles:
            user_id = request_data.get("user_id", "unknown")
            raise AuthorizationError(
                f"User {user_id} lacks required role: {required_role}. "
                f"User roles: {user_roles}"
            )

        logger.debug(f"User has required role: {required_role}")

    def require_permission(self, request_data: Dict, required_permission: str) -> None:
        """
        Check if user has required permission.

        Args:
            request_data: Authenticated request data
            required_permission: Required permission (e.g., "read:documents")

        Raises:
            AuthorizationError: If user lacks the permission
        """
        user_permissions = request_data.get("user_permissions", [])

        if required_permission not in user_permissions:
            user_id = request_data.get("user_id", "unknown")
            raise AuthorizationError(
                f"User {user_id} lacks required permission: {required_permission}. "
                f"User permissions: {user_permissions}"
            )

        logger.debug(f"User has required permission: {required_permission}")

    def require_any_role(self, request_data: Dict, roles: List[str]) -> None:
        """
        Check if user has any of the specified roles.

        Args:
            request_data: Authenticated request data
            roles: List of acceptable roles

        Raises:
            AuthorizationError: If user has none of the roles
        """
        user_roles = request_data.get("user_roles", [])

        if not any(role in user_roles for role in roles):
            user_id = request_data.get("user_id", "unknown")
            raise AuthorizationError(
                f"User {user_id} lacks any of required roles: {roles}. "
                f"User roles: {user_roles}"
            )

        logger.debug(f"User has one of required roles: {roles}")

    def require_tenant_access(self, request_data: Dict, resource_tenant_id: str) -> None:
        """
        Check if user's tenant matches resource tenant.

        Args:
            request_data: Authenticated request data
            resource_tenant_id: Tenant that owns the resource

        Raises:
            AuthorizationError: If tenant mismatch
        """
        user_tenant_id = request_data.get("tenant_id")

        if user_tenant_id != resource_tenant_id:
            raise AuthorizationError(
                f"Tenant {user_tenant_id} cannot access resources "
                f"owned by tenant {resource_tenant_id}"
            )

        logger.debug(f"Tenant access verified for resource: {resource_tenant_id}")


def create_auth_handler(
    jwt_handler: JWTHandler,
    required_roles: Optional[List[str]] = None,
    required_permissions: Optional[List[str]] = None
) -> Callable:
    """
    Create a request handler decorator with authentication and authorization.

    Args:
        jwt_handler: JWT handler instance
        required_roles: List of roles, user must have at least one
        required_permissions: List of permissions, user must have all

    Returns:
        Decorated handler function

    Example:
        >>> jwt_handler = JWTHandler(config)
        >>> auth_handler = create_auth_handler(
        ...     jwt_handler,
        ...     required_permissions=["read:documents"]
        ... )
        >>>
        >>> @auth_handler
        ... def my_endpoint(request_data):
        ...     # This will only execute if user is authenticated
        ...     # and has "read:documents" permission
        ...     return {"result": "success"}
    """
    middleware = AuthMiddleware(jwt_handler)

    def handler_wrapper(original_handler):
        def wrapped_handler(request_data: Dict, **kwargs):
            try:
                # Authenticate
                authenticated_request = middleware.authenticate_request(request_data)

                # Check roles if required
                if required_roles:
                    middleware.require_any_role(authenticated_request, required_roles)

                # Check permissions if required
                if required_permissions:
                    for permission in required_permissions:
                        middleware.require_permission(authenticated_request, permission)

                # Call original handler
                result = original_handler(authenticated_request, **kwargs)

                return result

            except AuthenticationError as e:
                logger.error(f"Authentication error: {e}")
                return {
                    "error": "authentication_failed",
                    "message": str(e),
                    "status_code": 401
                }

            except AuthorizationError as e:
                logger.error(f"Authorization error: {e}")
                return {
                    "error": "authorization_failed",
                    "message": str(e),
                    "status_code": 403
                }

            except Exception as e:
                logger.error(f"Unexpected error in auth handler: {e}", exc_info=True)
                return {
                    "error": "internal_error",
                    "message": "An unexpected error occurred",
                    "status_code": 500
                }

            finally:
                # Clean up context
                TenantContext.clear()

        return wrapped_handler

    return handler_wrapper


# Role definitions (can be extended)
class Roles:
    """Standard role definitions."""

    ADMIN = "admin"  # Full access to tenant
    EDITOR = "editor"  # Can read and write
    VIEWER = "viewer"  # Read-only access
    GUEST = "guest"  # Limited access


# Permission definitions (can be extended)
class Permissions:
    """Standard permission definitions."""

    # Document permissions
    READ_DOCUMENTS = "read:documents"
    WRITE_DOCUMENTS = "write:documents"
    DELETE_DOCUMENTS = "delete:documents"

    # Search permissions
    SEARCH = "search"
    ADVANCED_SEARCH = "advanced_search"

    # User management
    READ_USERS = "read:users"
    WRITE_USERS = "write:users"
    DELETE_USERS = "delete:users"

    # Settings
    READ_SETTINGS = "read:settings"
    WRITE_SETTINGS = "write:settings"

    # Analytics
    READ_ANALYTICS = "read:analytics"


# Role-to-permission mapping
ROLE_PERMISSIONS = {
    Roles.ADMIN: [
        Permissions.READ_DOCUMENTS,
        Permissions.WRITE_DOCUMENTS,
        Permissions.DELETE_DOCUMENTS,
        Permissions.SEARCH,
        Permissions.ADVANCED_SEARCH,
        Permissions.READ_USERS,
        Permissions.WRITE_USERS,
        Permissions.DELETE_USERS,
        Permissions.READ_SETTINGS,
        Permissions.WRITE_SETTINGS,
        Permissions.READ_ANALYTICS,
    ],
    Roles.EDITOR: [
        Permissions.READ_DOCUMENTS,
        Permissions.WRITE_DOCUMENTS,
        Permissions.SEARCH,
        Permissions.ADVANCED_SEARCH,
        Permissions.READ_USERS,
    ],
    Roles.VIEWER: [
        Permissions.READ_DOCUMENTS,
        Permissions.SEARCH,
    ],
    Roles.GUEST: [
        Permissions.READ_DOCUMENTS,
    ],
}


def get_permissions_for_roles(roles: List[str]) -> List[str]:
    """
    Get all permissions for a list of roles.

    Args:
        roles: List of role names

    Returns:
        Combined list of unique permissions
    """
    permissions = set()

    for role in roles:
        role_perms = ROLE_PERMISSIONS.get(role, [])
        permissions.update(role_perms)

    return list(permissions)
